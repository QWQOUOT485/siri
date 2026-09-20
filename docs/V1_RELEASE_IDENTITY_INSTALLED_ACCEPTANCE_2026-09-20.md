# v1.0.0 Installed Identity Acceptance Evidence

Date: 2026-09-20
Reviewed source `main`: `71eb1bb74365cf69a88ae84239b4fa7d14f06f33`
PR #32 reviewed head: `7e25596980552bdfd81549ed58772304694a380c`
Installed target: `D:\ai\windows-siri-agent`

## Verdict

**Installed v1.0.0 release-identity acceptance PASSED.**

This is an evidence-only record. It does not create a tag or GitHub Release,
and it does not accept deferred Spotify, Siri, Semantic Memory, or Local AI
work.

## Deployment boundary

- The reviewed `main` source was deployed after PR #32 merged.
- The deployment copied 161 tracked release-controlled source files and did
  not delete files from the installed target.
- `.env`, `config`, `runtime`, `logs`, `outputs`, `work`, `.venv`, and secrets
  were excluded from the deployment copy operation. The installed `.env`
  remained unchanged by the deployment, and the protected directories remained
  present.
- A reversible backup of existing target source files was created outside the
  installed target at
  `D:\ai\windows-siri-agent-deploy-backups\20260920-pr32-before-identity`.

## Identity and parity readback

- Source `VERSION`: `1.0.0`.
- Installed `VERSION`: `1.0.0`.
- Installed package `app.__version__`: `1.0.0`.
- Installed runtime version fallback: `1.0.0`.
- Installed FastAPI/OpenAPI metadata version: `1.0.0`.
- Release-controlled source/installed parity compared 161 files: zero missing
  files and zero SHA-256 mismatches.

## Test and runtime acceptance

- Source focused version identity test: **1 passed**.
- Installed focused version identity test: **1 passed**.
- Source full pytest: **307 passed**, with two existing dependency deprecation
  warnings.
- Installed full pytest: **307 passed**, with two existing dependency
  deprecation warnings.
- Source and installed `compileall`: passed.
- Source and installed `pip check`: passed.
- Installed Agent normal startup: passed; no startup traceback was present in
  the dedicated startup stderr capture.
- Loopback `GET /health`: HTTP 200, `version=1.0.0`.
- `/health` exposed exactly the bounded fields `ok`, `status`, `version`, and
  `uptime_seconds`.
- OpenAPI metadata: HTTP 200, `info.version=1.0.0`.

## Safety boundary

- Installed effective settings were `semantic_memory_enabled=false`,
  `LOCAL_AI_MODE=shadow`, and `LOCAL_AI_FALLBACK_APPROVED=false`.
- Local AI remained shadow-only and was not promoted to execution authority.
- No live Spotify request was made; all Spotify coverage came from mocked unit
  tests. No `spotify_continue` retry, Siri voice E2E, Candidate Recovery,
  Semantic Memory enablement, or Local AI promotion was performed.
- The formal `v1.0.0` tag and GitHub Release were not created.
