# Local AI Source/Unit Fail-Closed Matrix — 2026-09-20

This document records a reproducible, sanitized in-process matrix for the
guarded Local AI path. It does not authorize production fallback and does not
replace live Windows Agent, LM Studio, Spotify, or Siri acceptance.

## Boundary

The matrix uses fake adapters and a fake policy boundary inside the pytest
process. It does not read the installed Agent `.env`, call LM Studio, send a
Spotify request, create a playback action, or mutate an account. No raw model
output, token, API key, prompt, Spotify URI, or track ID is recorded.

The production state remains:

```text
LOCAL_AI_MODE=off or shadow
LOCAL_AI_FALLBACK_APPROVED=false
```

## Reproduction

From the repository root:

```text
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_local_ai.py tests/unit/test_local_ai_promotion_matrix.py
```

The matrix was added as `tests/unit/test_local_ai_promotion_matrix.py` and
passed together with the existing Local AI unit suite. The test file contains
no subprocess, network, or production-configuration path.

Current run result: `38 passed, 2 warnings` for the targeted Local AI command.
The warnings are the existing FastAPI/Starlette/httpx deprecations.

## Matrix results

| Failure or safety class | Controlled source/unit result | Action created |
|---|---|---|
| Malformed model JSON | strict schema rejection | No |
| Malformed schema with authority field | strict schema rejection | No |
| Connection/timeout category | bounded transport error | No |
| Connection refused at the adapter seam | `connection_or_timeout` category | No |
| Single-flight busy | bounded `busy` transport error | No |
| Oversized response | bounded `response_too_large` transport error | No |
| Ungrounded track | deterministic grounding rejection | No |
| Invented optional artist/album | optional slots removed before policy | No |
| Policy rejection | policy gate rejection | No |
| Shadow-mode accepted interpretation | result has no executable action | No |

The existing Local AI tests also cover loopback-only endpoint validation,
bounded request/response behavior, the strict closed schema, clarification
bypass, deterministic resolver retry, and fallback approval gating.

The full repository verification for this evidence update also passed:

```text
pytest -q                         246 passed, 2 warnings
compileall app scripts tests      passed
pip check                         No broken requirements found
git diff --check                  passed
```

## Evidence boundary and remaining blockers

These rows are source/unit evidence. They do not clear the independent review
blocker for a live transport fault matrix because the prior isolated
second-process fault-injection attempt was blocked before process start. They
also do not provide fresh Siri/real-account acceptance or independent
authorization for an exact executable-fallback configuration.

The independent promotion decision therefore remains **NO-GO**. Keep Local AI
off or shadow and keep `LOCAL_AI_FALLBACK_APPROVED=false`.
