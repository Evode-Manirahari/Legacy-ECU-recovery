# NODE: PROVIDER-001

**Title:** OpenAI provider transport
**Depends on:** `EVAL-AGENT-001`
**Verification:** commands
**Retry budget:** 2

## Goal

```text
ModelRequest -> live provider -> ModelResponse
```

Transport, and nothing else. This node does not capture, freeze, or score a
transcript; `BASELINE-AGENT-001` owns that. Keeping them apart means a transport
failure and a bad answer are never the same incident.

## Ownership

Allowed: `src/ecu_recovery/providers/openai/**`, `tests/providers/openai/**`,
`pyproject.toml`.

Its own tree, deliberately outside `src/ecu_recovery/agent/**`. `AGENT-001` owns
the protocol and the bounded reasoning path and is already verified; a provider
must not be able to reach into it.

`pyproject.toml` is included for **one line**: an optional `openai` extra. Do not
add it to `dependencies`. The default install and the whole test suite stay free
of it, exactly as they are of Ghidra.

Forbidden: `src/ecu_recovery/agent/**`, `src/ecu_recovery/evaluation/**`,
`artifacts/**`. If the protocol genuinely needs to change, report it as an
interface finding rather than editing around it.

## Fixed decisions

These are settled; do not re-litigate them in the implementation.

- **OpenAI, official Python client, Responses API**, behind the existing
  `ModelProvider.complete(ModelRequest) -> ModelResponse`. The protocol is
  unchanged.
- **API key from `OPENAI_API_KEY` only.** Never a constructor default, never a
  file, never a committed value.
- **Model name is configurable**, not buried in the adapter.
- **`store=False`.**
- **No tools, no streaming**, no web/search/file capability. One completion
  request in, text response out.
- **Transport retries disabled for baseline capture.** Configure the official
  client with `max_retries=0`, or the equivalent per-request setting. "One
  completion request" must mean one outbound attempt.
- The **exact model identifier** used must be recorded in the `ModelResponse` so
  it can reach every frozen transcript.
- The first committed baseline should use a **pinned GPT-5.6 Sol snapshot** if
  the API exposes one. Do not invent a snapshot name: if no pinned identifier is
  available, record what the API actually reports and say so.

## Required properties

1. **The protocol is unchanged and unwidened.** No streaming, no tool-calling.
   The model is handed facts, not the ability to fetch them, and that is what
   keeps retrieval deterministic and a wrong answer attributable.
2. **No new capability for the model.** No tool access, no filesystem, no shell.
   The adapter's only outward call is the completion request.
3. **No credential ever reaches disk or a log.** No key, token, or account
   identifier is committed, printed, or written into a response.
4. **The suite runs with nothing configured.** Provider-marked tests skip with a
   stated reason when the extra or the key is absent, exactly as the Ghidra
   tests do. A contributor without an account still gets a green, honest run.
5. **Failure is a value.** A refused request, a timeout, or an unusable reply
   arrives through the existing `ModelUnavailableError` path so `investigate`
   records it instead of crashing.
6. **One attempt means one attempt.** The SDK's own retry loop is off
   (`max_retries=0`). A timeout, a rate limit, or a server error flows through
   the failure path above and is frozen and reported by `BASELINE-AGENT-001`,
   rather than being silently absorbed by a retry nobody recorded. A hidden
   second attempt makes the capture a sample of the best of several tries while
   the transcript claims it was one.

   Model-level retries stay forbidden as already specified: the agent does not
   re-ask a model that answered badly.

   This does not forbid a deliberately started replacement run after a transport
   failure - `BASELINE-AGENT-001` already requires such a rerun to be recorded.
   It forbids invisible retries inside one supposedly singular attempt.
7. **Request construction is testable without a network.** The reply is not
   reproducible and is not expected to be; that is why it later gets frozen.

## Deliverables

The adapter, the optional extra, and tests covering request construction,
model-identity recording, error mapping, credential absence, and skip behaviour.

## Acceptance

```bash
uv run pytest
```

Green with no key and no extra installed.

## Exclusions

Do not capture or commit a transcript. Do not modify the agent or the evaluator.
Do not start `BASELINE-AGENT-001` or `GATE-AGENT-MVP`. No emulation.

## Stop

Return the structured handoff and stop.
