"""In-app live runs (ADR 0012): what a learner's code may ask the real model, what it costs,
and how much a learner may spend.

A live run executes an exercise's `live.py` over the learner's files in the sandbox. The sandbox
has no network and no key; every model call is a message to the worker's proxy, which checks it
against `LiveCall`, forces the platform's model, clamps `max_tokens`, enforces the run's limits
and the learner's spending caps, and records the cost. Grades never come from a live run.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lattice.domain.entitlements import Plan, is_paid

# Bounds on one call from the sandbox. A request is at most `MAX_REQUEST_BYTES` of JSON (about
# 100K tokens, past which Haiku's input price is five times higher).
MAX_REQUEST_BYTES = 400_000
MAX_TEXT = 200_000
MAX_MESSAGES = 200
MAX_TOOLS = 64
MAX_NAME = 128


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LiveToolCall(_Strict):
    id: str = Field(max_length=MAX_NAME)
    name: str = Field(max_length=MAX_NAME)
    arguments: dict[str, Any]


class LiveMessage(_Strict):
    role: Literal["user", "assistant", "tool"]
    content: str = Field(default="", max_length=MAX_TEXT)
    tool_calls: list[LiveToolCall] = Field(default_factory=list, max_length=MAX_TOOLS)
    tool_call_id: str | None = Field(default=None, max_length=MAX_NAME)

    @model_validator(mode="after")
    def _shape(self) -> LiveMessage:
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only assistant messages can contain tool calls")
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("tool messages, and only tool messages, need a tool_call_id")
        return self


class LiveTool(_Strict):
    name: str = Field(max_length=MAX_NAME)
    description: str = Field(max_length=MAX_TEXT)
    input_schema: dict[str, Any]


class LiveCall(_Strict):
    """One model call as learner code made it: `forgeway_kit`'s `Request`, minus `sample`.

    `model` is what the code asked for; the proxy always runs the platform's model instead.
    `temperature` is accepted and never sent (the API version rejects sampling parameters).
    """

    messages: list[LiveMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    system: str | None = Field(default=None, max_length=MAX_TEXT)
    max_tokens: int = Field(ge=1)
    temperature: float = 0.0
    tools: list[LiveTool] = Field(default_factory=list, max_length=MAX_TOOLS)
    model: str = Field(default="", max_length=MAX_NAME)
    response_format: dict[str, Any] | None = None
    tool_choice: Literal["auto", "any", "none"] | dict[str, str] = "auto"
    effort: Literal["low", "medium", "high"] | None = None

    @model_validator(mode="after")
    def _tool_choice(self) -> LiveCall:
        if isinstance(self.tool_choice, dict) and set(self.tool_choice) != {"name"}:
            raise ValueError("a tool_choice dict must be exactly {'name': '<tool name>'}")
        return self


@dataclass(frozen=True)
class ModelRate:
    """USD per million tokens. Above `long_above` input tokens, the `long_*` prices apply."""

    input: float
    output: float
    cache_read: float
    cache_write: float
    long_above: int | None = None
    long_input: float | None = None
    long_output: float | None = None


@dataclass(frozen=True)
class CallUsage:
    """Tokens one call used. `input_tokens` is the whole prompt, cache reads and writes included."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def cost_usd(usage: CallUsage, rate: ModelRate) -> float:
    """What a call cost at `rate`."""
    long = rate.long_above is not None and usage.input_tokens > rate.long_above
    input_price = rate.long_input if long and rate.long_input is not None else rate.input
    output_price = rate.long_output if long and rate.long_output is not None else rate.output
    fresh = max(usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens, 0)
    total = (
        fresh * input_price
        + usage.cache_read_tokens * rate.cache_read
        + usage.cache_write_tokens * rate.cache_write
        + usage.output_tokens * output_price
    )
    return total / 1_000_000


@dataclass(frozen=True)
class SpendPolicy:
    """How much a learner may spend on live runs (owner's decision, docs/plans/ai-tutor.md).

    A paid plan's monthly cap follows what the learner pays (`interval_caps_usd`, by billing
    interval); a paid plan with no billing behind it, granted by hand or with billing off, has
    `pro_monthly_cap_usd`. The free plan's is `free_monthly_usd` (none by default). A trial has
    `trial_usd` for the whole trial instead. Within the month, no more than `daily_fraction` of
    the cap may go in one day, so a runaway script cannot use the month in an hour. Months and
    days are UTC calendar periods.
    """

    pro_monthly_cap_usd: float
    daily_fraction: float
    free_monthly_usd: float
    trial_usd: float = 1.0
    interval_caps_usd: Mapping[str, float] = field(default_factory=dict)

    def monthly_cap(self, plan: Plan, interval: str | None = None) -> float:
        if is_paid(plan):
            return self.interval_caps_usd.get(interval or "", self.pro_monthly_cap_usd)
        return self.free_monthly_usd

    def daily_cap(self, plan: Plan, interval: str | None = None) -> float:
        return self.monthly_cap(plan, interval) * self.daily_fraction


def month_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(now: datetime) -> datetime:
    start = month_start(now)
    return (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )


def day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Allowance:
    """A learner's live-run spending: what they may spend and have spent, month and day."""

    monthly_cap_usd: float
    spent_month_usd: float
    daily_cap_usd: float
    spent_today_usd: float
    now: datetime
    # Set during a trial: the "month" figures are then the whole trial's, until this moment.
    trial_end: datetime | None = None

    @property
    def remaining_usd(self) -> float:
        return max(
            min(
                self.monthly_cap_usd - self.spent_month_usd,
                self.daily_cap_usd - self.spent_today_usd,
            ),
            0.0,
        )

    @property
    def exhausted(self) -> Literal["month", "day"] | None:
        """Which cap stops the next call, if any (the month's first, as it lasts longer)."""
        if self.spent_month_usd >= self.monthly_cap_usd:
            return "month"
        if self.spent_today_usd >= self.daily_cap_usd:
            return "day"
        return None

    @property
    def resets_at(self) -> datetime:
        """When more becomes available: the next month if the month is spent, else tomorrow."""
        if self.exhausted == "month":
            return self.trial_end or next_month(self.now)
        return day_start(self.now) + timedelta(days=1)


@dataclass(frozen=True)
class LiveLimits:
    """Per-run limits the proxy enforces."""

    max_calls: int
    max_tokens: int  # input plus output, over the whole run
    max_output_tokens_per_call: int
    timeout_s: int
    max_output_bytes: int = 16 * 1024


@dataclass(frozen=True)
class LiveConfig:
    """Everything the API and the worker need to know about live runs, from settings."""

    enabled: bool
    model: str
    rates: Mapping[str, ModelRate]
    policy: SpendPolicy
    limits: LiveLimits
    runs_per_hour: int
    seconds_per_day: int = 600  # time a learner's runs may hold the worker in any 24 hours

    @property
    def rate(self) -> ModelRate:
        return self.rates[self.model]


@dataclass(frozen=True)
class LiveSandboxRequest:
    """A live run for the sandbox: the learner's files laid over the starter, and `live.py`."""

    runtime: str
    files: dict[str, str]
    nonce: str
    timeout_s: int
    memory_mb: int
    max_output_bytes: int


@dataclass(frozen=True)
class LiveSandboxResult:
    exit_status: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False
    # "no-live-script", "bad-message", "channel-closed", "protocol" (the container broke the
    # channel's rules) or "no-report"; None when the program ran to its end.
    error: str | None = None
    duration_ms: int = 0
    container_stderr: str = ""


class ProviderError(Exception):
    """The provider refused or failed. `kind` is "rate_limit", "server" or "invalid"."""

    def __init__(self, kind: str, message: str, retry_after_s: float = 1.0) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after_s = retry_after_s


@dataclass(frozen=True)
class ProviderReply:
    completion: dict[str, Any]  # the toolkit's Completion, as JSON for the sandbox
    usage: CallUsage
    model: str
    latency_ms: int


class ModelProvider(Protocol):
    """The platform's model, holding the platform's key. Raises `ProviderError`."""

    def complete(
        self, call: LiveCall, *, model: str, max_tokens: int, timeout_s: float | None = None
    ) -> ProviderReply:
        """`timeout_s`: the most this one call may take, so a run cannot outlive its deadline."""
        ...


class Proxy(Protocol):
    """A call frame's request from the container in, the reply line's body out
    (``{"completion": ...}`` or ``{"error": {...}}``). It never raises for learner input.
    `timeout_s` is what is left of the run for this call."""

    def __call__(self, body: Any, *, timeout_s: float | None = None) -> dict[str, Any]: ...


class LiveSandboxRunner(Protocol):
    """Runs a live run in isolation, relaying each model call to `proxy`."""

    def run_live(self, request: LiveSandboxRequest, proxy: Proxy) -> LiveSandboxResult: ...


@dataclass
class RunMeter:
    """What one run has used so far, for its per-run limits."""

    limits: LiveLimits
    calls: int = 0
    tokens: int = 0
    records: list[dict[str, Any]] = field(default_factory=list)

    def refusal(self) -> str | None:
        """Why the run may make no more calls, or None."""
        if self.calls >= self.limits.max_calls:
            return (
                f"This live run has made its {self.limits.max_calls} model calls, the most one "
                "run may make."
            )
        if self.tokens >= self.limits.max_tokens:
            return (
                f"This live run has used its {self.limits.max_tokens:,} tokens, the most one run "
                "may use."
            )
        return None
