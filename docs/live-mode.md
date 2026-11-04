# Live mode: run your code against a real model

Every exercise on Forgeway is graded against deterministic fakes, so a pass means the same for
everyone and costs nothing. Live mode is the other half: you take the same code to your own
machine and run it against a real model, with your own API key, to see how it behaves for real.

**Forgeway never receives, stores or asks for your key.** There is no key field anywhere on the
site. Your key lives in your own environment; the toolkit reads it there when a client is made
and sends it only to the provider you chose. It is never written to disk, logged, or sent to
Forgeway.

## 1. Download the exercise

In the workspace, under the editor, choose **Run locally** (in RPG mode, **Take it to your own
forge**). You get a zip named after the exercise, holding:

- `brief.md`, the exercise brief;
- your current code: your draft if you have one, otherwise the starter files, exactly as the
  workspace shows them;
- `live.py`, when the exercise has one: a short script that runs your code against a live client;
- `README.md`, a short version of this guide with the exact install command;
- `LIVE-MODE.md`, this guide in full. It is also on the site at
  [forgeway.dev/live-mode](https://forgeway.dev/live-mode).

The zip never holds the hidden tests, the reference solution or the known-wrong cases. A Pro
exercise downloads only on a plan that includes it, as with running its checks.

## 2. Install the toolkit

Your code imports `forgeway_kit`, the same toolkit the grader uses. Forgeway serves it as a
wheel; the README in your zip and the **Run locally** panel give the exact URL. Use Python 3.12 or
newer, ideally in a virtual environment:

```sh
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install "https://forgeway.dev/kit/forgeway_kit-<version>-py3-none-any.whl"
```

`https://forgeway.dev/kit/latest` redirects to the current wheel, for a browser or `curl -LO`;
`pip` needs the versioned file name itself. The toolkit has no dependencies outside the standard
library: the live clients talk to the providers' HTTP APIs directly, with no SDK.

## 3. Choose a provider

Live mode is switched on by environment variables. Set them in your shell (in PowerShell,
`$env:NAME = "value"`), or in a `.env` loader of your own; never in your code, and never in a file
you commit.

- **`FORGEWAY_LIVE`**: `anthropic`, `openai` or `openai-compatible`. Unset, `default_client()`
  has no client to give you and raises `RuntimeError: no model client is configured`; any other
  value raises too.
- **`ANTHROPIC_API_KEY`**: your Anthropic key, required for `anthropic`.
- **`OPENAI_API_KEY`**: your OpenAI key, required for `openai`. For `openai-compatible` it is
  optional: sent as a bearer token if set, which most local servers ignore.
- **`FORGEWAY_MODEL`**: the model to call. Required for `openai` and `openai-compatible`; for
  `anthropic` it defaults to `claude-opus-5-5`.
- **`FORGEWAY_BASE_URL`**: the server, required for `openai-compatible`. With `anthropic` or
  `openai` it is optional and replaces the provider's own address, for a proxy.

### Anthropic

```sh
export FORGEWAY_LIVE=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export FORGEWAY_MODEL=claude-sonnet-5-5     # optional; claude-opus-5-5 if unset
```

`AnthropicClient` uses the Messages API. It does not send `temperature`, which the API version it
speaks rejects; `effort` and `response_format` go in `output_config`.

### OpenAI

```sh
export FORGEWAY_LIVE=openai
export OPENAI_API_KEY=sk-...
export FORGEWAY_MODEL=gpt-4.1-mini          # required
```

`OpenAIClient` uses Chat Completions. `effort` becomes `reasoning_effort` and `response_format` a
strict `json_schema` format. The toolkit has no prices for OpenAI models, so the cost line reads
"cost unknown" (see section 5).

### Local models: Ollama, LM Studio and other OpenAI-compatible servers

`openai-compatible` is `OpenAIClient` pointed at your own server. Nothing leaves your machine at
all, and nothing is billed, at the price of smaller models.

```sh
ollama pull llama3.2
export FORGEWAY_LIVE=openai-compatible
export FORGEWAY_BASE_URL=http://localhost:11434/v1     # LM Studio: http://localhost:1234/v1
export FORGEWAY_MODEL=llama3.2
```

Small local models follow tool-use and structured-output instructions less reliably than the
large hosted ones. That is worth seeing, and it is the kind of failure the exercises teach you to
handle.

### Check it works

```sh
python -m forgeway_kit.live check
```

builds a client from the variables above (ignoring any client your own code would configure),
sends one message, "Reply with the single word: ready", with `max_tokens=256` (and `effort="low"`
for Anthropic), and prints `<model>: '<reply>' (stop: <reason>)` on stdout, with the usual cost
line on stderr. It is a real, billed call, though a tiny one. If the settings are incomplete or the
provider refuses (a wrong key, an unknown model, a server that is not running), it prints
`live check failed: <reason>` to stderr and exits with status 1.

## 4. Run your code

If the exercise has a `live.py`, run it from the unzipped folder:

```sh
python live.py
```

Otherwise call your own code with a live client. Exercise code takes its client as an argument or
calls `default_client()`, so nothing in it changes:

```python
from forgeway_kit import default_client

client = default_client()  # a live client, because FORGEWAY_LIVE is set
print(answer(client, "What does the refund policy say about opened items?"))
```

`default_client()` returns, in order: the client set with `use_client(...)`, if one is (that is
how the checks give your code its fake); otherwise, outside grading and with `FORGEWAY_LIVE` set,
a metered live client built from `FORGEWAY_LIVE`, `FORGEWAY_MODEL` and `FORGEWAY_BASE_URL`, made
once and reused for the rest of the process; otherwise it raises `no model client is configured`.
Inside the grader `FORGEWAY_LIVE` is ignored and live clients refuse to be made, whatever your
environment says. A client you build yourself (`AnthropicClient(...)` or `OpenAIClient(...)` from
`forgeway_kit.live`) works too and still reads its key only from the environment; wrap it in
`Metered(...)` to get the cost line.

The live clients implement the same interface as the fake, including `stream()` and the keyword
arguments the exercises use (`model`, `response_format`, `tool_choice`, `effort`), so code that
passes against the fake runs unchanged, with one exception worth knowing:

- **Use `tool_choice="auto"` with current Claude models.** A forced choice, `"any"` or
  `{"name": ...}`, gets a 400 (`InvalidRequestError`) from Claude Opus 5.5 and Sonnet 5.5. Ask
  for the tool in the prompt and check the reply instead, as you would for any model that might
  answer in text. `"auto"` and `"none"` work everywhere.

## 5. Reading the cost and latency output

The client `default_client()` builds is wrapped in `Metered`, which prints one line to stderr for
every call (for a stream, when it ends):

```text
[forgeway] claude-opus-5-5  in 1840 (cache 1536)  out 212 (reasoning 0)  2310 ms  ~$0.0058
```

That is the model, the input tokens (the whole prompt, cache reads included) with the cache reads
in brackets, the output tokens with reasoning tokens in brackets (OpenAI reports these; Anthropic
counts thinking inside the output), the latency and an estimated cost. Your program's own output on
stdout is untouched, so you can redirect either one.

Use it the way the exercises on cost and latency teach:

- **Add it up per task, not per call.** An agent turn, an eval case or a research question is
  many calls. A guided project's eval suite multiplies that by every case.
- **Watch cache reads.** A stable prefix (system prompt and tools first, then the conversation)
  shows up as cache reads on the second and later calls, billed at a fraction of the input price.
- **Latency is a distribution.** Time a whole run several times and look at the slow tail, not
  one call.
- **The cost is an estimate.** It comes from the per-million-token prices in
  `forgeway_kit.live.DEFAULT_RATES`, which covers `claude-opus-5-5`, `claude-sonnet-5-5` and
  `claude-fable-5-1` only. Any other model prints `cost unknown (pass Metered(rates=...))`; pass
  your own `(input, output, cache read)` prices that way if you want an estimate. Cache writes are
  counted at the input price, so on a run that writes a lot of cache the estimate is low. Your
  provider's bill is the record. For a local model, read the tokens and latency; nothing is billed.

Set limits before a long run: the exercises' `token_budget`, `max_steps` and suite sizes exist for
exactly this. Start with a small smoke suite.

## 6. Expect nondeterminism

A real model does not give the same reply twice, even at temperature 0 where a provider still
accepts one, and providers change models under the same name. So:

- one run is a sample, not a result: repeat a case before deciding it is fixed or broken;
- eval specs should accept what is acceptable rather than one exact string or trajectory;
- judge with intervals (the bootstrap interval in the evals track) rather than a single mean;
- rate limits and transient server errors happen: handle `RateLimitError` and `ServerError` with
  backoff, as the retries exercise teaches, and do not count a rate-limited case as a failure.

## 7. Why grades stay on the fakes

Forgeway grades every attempt in a sandbox with no network, against seeded fakes, and it always
will:

- **Fair.** A pass means your code handles the cases the checks describe, not that a model happened
  to cooperate today. Everyone is graded on the same replies.
- **Testable failure.** The fakes can produce exactly the hard cases (a refusal, a malformed tool
  call, a stream that breaks halfway, a rate limit) on demand. A real model produces them only
  sometimes.
- **Free and private.** Grading never spends your money, and never needs your key, so Forgeway has
  no key to hold or lose.

A live run counts for nothing on the site. To make progress, paste your code back into the
workspace and run the checks there.

## Troubleshooting

- **`ModuleNotFoundError: forgeway_kit`**: install the wheel into the same environment you run
  `python` from.
- **`RuntimeError: no model client is configured`**: `FORGEWAY_LIVE` is not set in this shell.
- **`set FORGEWAY_MODEL to the model to use`** or **`set FORGEWAY_BASE_URL to the server`**:
  `openai` needs a model, and `openai-compatible` needs both.
- **The fake answers instead of a model**: your code passes its own `FakeModel`, or wraps the call
  in `use_client(...)`.
- **400 mentioning `tool_choice`**: use `"auto"` with current Claude models (section 4).
- **`cost unknown`**: the model is not in `DEFAULT_RATES`; that is expected for OpenAI and local
  models (section 5).
- **401 or authentication errors**: the key variable is unset or wrong for the provider. Check with
  `python -m forgeway_kit.live check`.
- **`could not reach http://localhost:...`** with `openai-compatible`: the local server is not
  running. A 404 from it usually means `FORGEWAY_BASE_URL` lacks the `/v1` suffix.
- **The zip has the wrong code**: the download takes your last saved draft; wait for *Draft saved*
  under the editor before downloading.

## In the app: Try it live

Some exercises can also run live without leaving Forgeway. Under the editor, **Try it live**
(in RPG mode, **Consult the oracle**) runs your current code, unsaved edits included, with the
exercise's `live.py` against a real model. It needs no key and no install, and nothing on this
page changes: local live mode with your own key works as before.

- **Forgeway's model, Forgeway's cost.** Every in-app call runs on Claude Haiku 5.5
  (`claude-haiku-5-5`), paid for by Forgeway, whatever model your code asks for. Your own key is
  never used or asked for. `max_tokens` is capped per call (1,024 by default), and a run may make
  at most 20 calls and use at most 60,000 tokens in 60 seconds.
- **The same code.** Your code runs in the grading sandbox, which has no network. Its client is
  the one `default_client()` returns there: every call goes to Forgeway's proxy outside the
  sandbox, which adds the key and makes the call. A call the proxy refuses (too big, over a
  limit, not a model call) reaches your code as `InvalidRequestError`; the provider's own rate
  limits and outages as `RateLimitError` and `ServerError`, as in local mode. `stream()` works,
  but delivers the reply only once it is complete.
- **What you see.** Your program's output and errors (the first 16 KB of each), then a table of
  every model call with its model, tokens, cost and latency, the run's total, and how much of
  your allowance is left and when more becomes available.
- **Allowance.** Live runs are part of Pro. Each month you may spend up to half of what you pay
  for Pro on them, and no more than a tenth of that in one day (UTC); a free trial has a smaller
  allowance for the whole trial. Your runs may also take up to ten minutes in any 24 hours. At any
  of these the run is refused with a message saying when more becomes available; your checks, and local live mode, are
  unaffected. The free plan has none unless the server grants a small allowance.
- **Your data.** Before your first live run you are shown, and acknowledge, where its data
  goes: your current files and the messages your program sends go to Anthropic, PBC in the
  United States, which runs the model as Forgeway's processor. Anthropic does not train on them
  and deletes them within 30 days (up to 2 years only if its safety systems flag them).
  Forgeway keeps each run's files and output for 30 days and its usage records for 13 months.
- **Grades still come from the checks.** A live run never passes or fails anything; run the
  checks to make progress.

If an exercise has no `live.py`, the button says so: use **Run locally** and call your code
yourself. How it is built, and why the key can never reach your code, is in
[ADR 0012](adr/0012-in-app-live-runs.md).
