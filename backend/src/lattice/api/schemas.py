"""Request and response bodies. These define the OpenAPI contract the frontend is generated from."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from lattice.domain.content import BranchKind

Mode = Literal["rpg", "professional"]
PlanName = Literal["free", "pro", "team"]
ColourScheme = Literal["system", "light", "dark"]
ExerciseStatus = Literal["locked", "available", "passed"]
FilesSource = Literal["starter", "draft", "carried"]
AttemptStatus = Literal["queued", "running", "passed", "failed", "errored"]
Files = Annotated[dict[str, str], Field(max_length=10)]


class ProblemTalent(BaseModel):
    id: str
    title: str
    path: str | None = None  # the specialisation it belongs to; None when every path shares it


class Problem(BaseModel):
    """RFC 9457 problem details, with optional structured extensions."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    # Reference-solution 403 only: the talents that unlock it, so a client words the hint itself.
    talents: list[ProblemTalent] | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=10, max_length=200)]
    display_name: Annotated[
        str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)
    ]
    time_zone: Annotated[str, StringConstraints(max_length=64)] | None = (
        None  # IANA, e.g. Europe/London
    )
    # The mode and scheme the visitor chose before the account existed, so they carry over.
    mode: Mode | None = None
    colour_scheme: ColourScheme | None = None
    # The Turnstile widget's `cf-turnstile-response`; required only while Turnstile is on.
    turnstile_token: Annotated[str, StringConstraints(max_length=2048)] | None = None
    # "I am 18 or over": must be true (Forgeway is for adults only).
    over_18: bool
    # The unticked "no offers" box, ticked: refuses marketing email from the start.
    marketing_opt_out: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(max_length=200)]


Password = Annotated[str, StringConstraints(min_length=10, max_length=200)]
Token = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class VerifyEmailRequest(BaseModel):
    token: Token


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetCheck(BaseModel):
    token: Token


class PasswordResetConfirm(BaseModel):
    token: Token
    password: Password


class EmailChangeRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(max_length=200)]  # the current password


class IntroOffer(BaseModel):
    kind: Literal["trial_days"]
    value: int  # days


class BillingConfig(BaseModel):
    """What the pricing pages need. Prices are in pence and include VAT."""

    enabled: bool  # false: no prices are on sale and the Pro waitlist shows instead
    currency: Literal["GBP"]
    monthly_price_minor: int
    annual_price_minor: int
    intro_offer: IntroOffer | None  # the free trial new subscribers get; null when there is none


class PublicConfig(BaseModel):
    turnstile_site_key: str | None
    free_exercises_per_branch: int  # the free plan's exercises per track, past the foundations
    kit_wheel_url: str | None  # `pip install` this for local live mode; null: none built
    live_runs: bool = False  # in-app live runs on Forgeway's model are switched on (ADR 0012)
    live_model: str | None = None  # the model every in-app live run uses, when switched on
    billing: BillingConfig
    trader_address: str | None = None  # for the legal pages; null: not set yet


class OutboxToken(BaseModel):
    subject: str
    token: str


class TestPlan(BaseModel):
    """Test-only (`/api/test/plan`): put an account on a plan."""

    email: str
    plan: PlanName


class Profile(BaseModel):
    mode: Mode
    colour_scheme: ColourScheme
    marketing_opt_out: bool  # refused offers by email
    new_to_python: bool  # show the "Python you'll need" notes on exercises


class ProfileUpdate(BaseModel):
    mode: Mode | None = None
    colour_scheme: ColourScheme | None = None
    marketing_opt_out: bool | None = None
    new_to_python: bool | None = None


class TermsAcceptance(BaseModel):
    version: Annotated[str, StringConstraints(max_length=32)]  # the version shown


class MarketingUnsubscribe(BaseModel):
    token: Token


class Me(BaseModel):
    id: uuid.UUID
    email: str
    # Unverified learners can sign in and explore, but not submit attempts or publish
    # certificates until they follow the link emailed to them.
    email_verified: bool
    pending_email: str | None  # a requested new address, until its link is followed
    display_name: str
    # What the learner may attempt. Every account starts free; there is no billing yet.
    plan: PlanName
    profile: Profile
    # False once the terms change materially after the learner accepted them: ask again.
    terms_current: bool
    csrf_token: str


class Level(BaseModel):
    level: int
    total_xp: int
    level_floor: int
    next_level_at: int | None
    fraction: float


class ExerciseSummary(BaseModel):
    id: str
    title: str
    tier: str
    xp: int
    skills: list[str]
    prerequisites: list[str]
    # Locked by prerequisites is `status`; locked by plan is `entitled` false. `pro` marks the
    # exercise as Pro content whatever the learner's plan.
    status: ExerciseStatus
    pro: bool
    entitled: bool


class BranchSummary(BaseModel):
    id: str
    title: str
    summary: str
    unlocked: bool
    requires: list[str]
    kind: BranchKind
    passed_count: int
    pro: bool  # every exercise in it is Pro (guided projects)
    exercises: list[ExerciseSummary]


class Streak(BaseModel):
    current: int
    longest: int


class LearnerMap(BaseModel):
    branches: list[BranchSummary]
    level: Level
    streak: Streak


class Catalogue(BaseModel):
    """Every branch as a brand-new learner on the free plan sees it. Public: nothing personal."""

    branches: list[BranchSummary]


class CheckInfo(BaseModel):
    id: str
    title: str
    kind: str


class AttemptSummary(BaseModel):
    id: uuid.UUID
    status: AttemptStatus
    created_at: datetime


class ExerciseDetail(BaseModel):
    id: str
    branch: str
    title: str
    tier: str
    xp: int
    status: ExerciseStatus
    # Pro content, and whether this learner's plan lets them attempt it. Not entitled: the brief,
    # files, checks and hints are empty, and attempts answer 403 `plan-required`.
    pro: bool
    entitled: bool
    prerequisites: list[str]
    brief: str
    editable: list[str]
    files: dict[str, str]
    # "carried": the learner's own files from their latest passing attempt of `carried_from`, for
    # the paths it had; any other path is this exercise's starter.
    files_source: FilesSource
    carried_from: str | None
    checks: list[CheckInfo]
    hints_total: int
    hints_revealed: list[str]
    recent_attempts: list[AttemptSummary]
    # The exercise has a `live.py`, so "Try it live" can run it (ADR 0012).
    has_live_example: bool = False
    # `python.md`: the "Python you'll need" notes. Paid content like the brief, so empty when not
    # entitled; also empty when the exercise has none.
    python_notes: str = ""


class Hints(BaseModel):
    hints_revealed: list[str]
    hints_total: int


class FilesBody(BaseModel):
    files: Files


class CheckResult(BaseModel):
    id: str
    title: str
    passed: bool
    message: str
    output: str


class XpAwardOut(BaseModel):
    reason: str
    amount: int


class BadgeAwarded(BaseModel):
    id: str
    title: str
    description: str


class CertificateIssued(BaseModel):
    id: str
    branch_id: str
    branch_title: str
    includes_capstone: bool = False


class Progression(BaseModel):
    """What a graded attempt changed. Failed attempts carry no XP but can earn badges."""

    xp_awarded: int
    awards: list[XpAwardOut]
    level_before: int
    level_after: int
    unlocked: list[str]
    badges_awarded: list[BadgeAwarded] = []
    certificates_issued: list[CertificateIssued] = []
    talent_points_gained: int = 0
    streak: Streak | None = None  # absent on attempts graded before streaks existed


class AttemptDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise_id: str
    status: AttemptStatus
    created_at: datetime
    finished_at: datetime | None
    checks: list[CheckResult] = []
    error: str | None = None
    duration_ms: int | None = None
    progression: Progression | None = None

    @classmethod
    def from_row(cls, row: Any) -> AttemptDetail:
        report: dict[str, Any] = row.report or {}
        return cls(
            id=row.id,
            exercise_id=row.exercise_id,
            status=row.status,
            created_at=row.created_at,
            finished_at=row.finished_at,
            checks=report.get("checks", []),
            error=report.get("error"),
            duration_ms=report.get("duration_ms"),
            progression=report.get("progression"),
        )


class BranchRef(BaseModel):
    id: str
    title: str


class PathOption(BaseModel):
    id: str
    title: str
    summary: str
    home_branch: str | None
    selectable: bool
    reason: str | None
    # The branches to complete before it can be chosen; empty once it is selectable.
    requires: list[BranchRef] = []


class PathProfile(BaseModel):
    path: str
    time_zone: str
    titles: list[str]
    paths: list[PathOption]
    dropped_talents: list[str] = []  # talents lost by the change that produced this response


class PathProfileUpdate(BaseModel):
    """Only the fields supplied change."""

    path: str | None = None
    time_zone: Annotated[str, StringConstraints(max_length=64)] | None = None


class Blocker(BaseModel):
    code: str
    detail: str


class TalentEffect(BaseModel):
    kind: Literal["title", "reference_solutions"]
    value: str  # the title, or the branch id


class TalentNode(BaseModel):
    id: str
    title: str
    summary: str
    subtree: str
    parents: list[str]
    min_level: int
    required_exercises: list[str]
    effects: list[TalentEffect]
    state: Literal["allocated", "available", "locked"]
    reasons: list[Blocker]  # why a node is locked; empty otherwise


class TalentTree(BaseModel):
    path: str
    total_points: int
    spent_points: int
    available_points: int
    nodes: list[TalentNode]


class BadgeRequirement(BaseModel):
    """A badge's criterion as data, so a client can word it in its own vocabulary."""

    kind: str
    n: int | None = None  # the count, for every kind but branch_complete
    branch: BranchRef | None = None  # for branch_complete


class BadgeStatus(BaseModel):
    id: str
    title: str
    description: str
    criterion: str  # how it is earned, in words
    requirement: BadgeRequirement
    earned: bool
    awarded_at: datetime | None
    attempt_id: uuid.UUID | None


class BadgeList(BaseModel):
    badges: list[BadgeStatus]


class ReferenceSolution(BaseModel):
    files: dict[str, str]
    notes: str


PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    code: {"model": Problem, "description": description}
    for code, description in {
        401: "Not signed in",
        403: "Forbidden (locked exercise, `plan-required`, CSRF or cross-origin)",
        404: "Not found",
        409: "Conflict",
        422: "Invalid input",
        429: "Rate limited",
        503: "Busy: the grading queue is full (with Retry-After)",
    }.items()
}


class LinkedInFields(BaseModel):
    """What LinkedIn's add-certification form takes, so the client can prefill it."""

    name: str
    organisation: str
    issue_year: int
    issue_month: int
    credential_id: str
    credential_url: str


class Certificate(BaseModel):
    id: str
    branch_id: str
    branch_title: str
    recipient_name: str
    exercise_count: int
    includes_capstone: bool
    issued_at: datetime
    is_public: bool
    published_at: datetime | None
    public_url: str
    image_url: str
    linkedin: LinkedInFields


class CertificateList(BaseModel):
    certificates: list[Certificate]


class CertificateUpdate(BaseModel):
    is_public: bool | None = None
    # Trimmed and checked (1 to 60 characters, no control characters) by the use case.
    recipient_name: Annotated[str, StringConstraints(max_length=200)] | None = None


class PublicCertificate(BaseModel):
    """The public view. No account data: only what the certificate attests."""

    id: str
    recipient_name: str
    branch_title: str
    exercise_count: int
    includes_capstone: bool
    issued_at: datetime
    url: str
    image_url: str


class WaitlistJoin(BaseModel):
    plan: Literal["pro", "team"] = "pro"


class AccountDeletion(BaseModel):
    password: Annotated[str, StringConstraints(max_length=200)]  # the current password


class AccountExport(BaseModel):
    """Everything held about the learner, as the data export returns it. Times are ISO
    8601 strings. Password, session and emailed-link hashes are left out on purpose."""

    format: Literal["forgeway-account-export"]
    version: int
    exported_at: str
    account: dict[str, Any]
    profile: dict[str, Any] | None
    sessions: list[dict[str, Any]]
    emailed_links: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    drafts: list[dict[str, Any]]
    exercise_progress: list[dict[str, Any]]
    xp_events: list[dict[str, Any]]
    talents: list[dict[str, Any]]
    badges: list[dict[str, Any]]
    certificates: list[dict[str, Any]]
    live_runs: list[dict[str, Any]] = []
    live_calls: list[dict[str, Any]] = []
    live_notice_acknowledgements: list[dict[str, Any]] = []
    waitlist: dict[str, Any] | None
    billing: dict[str, Any] | None = None  # the subscription mirror and consent records
    rate_limit_records: list[dict[str, Any]]


class WaitlistStatus(BaseModel):
    joined: bool
    plan_interest: Literal["pro", "team"] | None
    joined_at: datetime | None


class ReleaseExercise(BaseModel):
    id: str
    title: str
    branch: str


class Release(BaseModel):
    version: str
    date: date
    title: str
    summary: str
    body: str  # Markdown
    added: list[ReleaseExercise]
    updated: list[ReleaseExercise]
    fixed: list[ReleaseExercise]


class ReleaseList(BaseModel):
    """Content releases, newest first, and whether the learner has one they have not seen."""

    releases: list[Release]
    last_seen: str | None
    unread: bool


LiveRunStatus = Literal["queued", "running", "finished", "errored"]
# finished: the program ran to its end (whatever its exit status); timed-out and stopped: the
# run was ended (too long, or something other than a model call on the live channel).
LiveOutcome = Literal["finished", "timed-out", "stopped", "errored", "no-live-example"]


class LiveAllowance(BaseModel):
    """A learner's live-run spending, in USD, for the UTC month and day."""

    monthly_cap_usd: float
    spent_month_usd: float
    daily_cap_usd: float
    spent_today_usd: float
    remaining_usd: float
    exhausted: Literal["month", "day"] | None
    resets_at: datetime  # when more becomes available


class LiveCallSummary(BaseModel):
    """One proxied model call: the model it ran on, its tokens, cost and latency."""

    model: str
    requested_model: str | None = None  # what the code asked for; the run always uses `model`
    max_tokens: int = 0  # after clamping
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    outcome: str = "ok"  # or the provider's error: "rate_limit", "server", "invalid"


class LiveRunDetail(BaseModel):
    id: uuid.UUID
    exercise_id: str
    status: LiveRunStatus
    created_at: datetime
    finished_at: datetime | None
    outcome: LiveOutcome | None = None
    message: str | None = None
    exit_status: int | None = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    duration_ms: int | None = None
    calls: list[LiveCallSummary] = []
    total_cost_usd: float = 0.0
    allowance: LiveAllowance


BillingInterval = Literal["monthly", "annual"]


class BillingConsentWording(BaseModel):
    """The regulation-37 consent, shown beside one checkbox before Checkout. Send `version` back
    with the checkout request."""

    version: str
    express: str
    acknowledgement: str


class SubscriptionInfo(BaseModel):
    # Stripe's status: trialing, active, past_due, canceled, unpaid, paused, incomplete, …
    status: str
    interval: BillingInterval | None
    paused: bool  # our pause: no payments and no Pro until `resumes_at`
    resumes_at: datetime | None
    trial_end: datetime | None  # set while trialing
    current_period_end: datetime | None  # the next renewal, or the end of a cancelled period
    cancelling: bool  # cancelled, with Pro kept until `ends_at`
    ends_at: datetime | None
    # The "Withdraw from contract" control: EU customers within 14 days of the contract, and
    # from 2027 anyone within 14 days of a trial converting or an annual renewal.
    withdrawal_until: datetime | None


class BillingStatus(BaseModel):
    enabled: bool
    plan: PlanName
    trial_days: int  # the free trial this learner would get now; 0 after a first subscription
    subscription: SubscriptionInfo | None
    consent: BillingConsentWording


class CheckoutStart(BaseModel):
    plan: BillingInterval
    consent: bool  # the regulation-37 checkbox, ticked
    consent_version: Annotated[str, StringConstraints(max_length=32)]
    # The unticked "no offers" box, ticked: refuses marketing email. Unticked changes nothing.
    marketing_opt_out: bool = False


class BillingPause(BaseModel):
    months: int = Field(default=1, ge=1, le=3)


class BillingRedirect(BaseModel):
    url: str  # where to send the browser: Stripe Checkout or the Customer Portal


class LiveNotice(BaseModel):
    """Where a live run's data goes: shown, and acknowledged, before a learner's first run."""

    version: str
    text: str
    acknowledged: bool


class LiveNoticeAcknowledgement(BaseModel):
    version: str = Field(max_length=32)
