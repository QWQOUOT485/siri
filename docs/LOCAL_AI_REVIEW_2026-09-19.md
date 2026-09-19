# Local AI Independent Gate Review — 2026-09-19

## Review scope

Static architecture/security review of the Local AI area on `main` through commit `718a5449366031ff43bd283ed7e3d1d97a7873db`.

Reviewed:

- `AGENTS.md`
- `PROJECT_STATUS.md`
- `docs/SOURCE_SPEC.md`
- `docs/SPEC.md`
- `docs/SECURITY.md`
- `docs/ARCHITECTURE.md`
- `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md`
- `docs/LOCAL_AI_MODEL_POC_RUNBOOK.md`
- Local AI domain/service/adapter/runtime/API/config code
- Local AI unit/API tests
- the latest guarded-semantic-scope and safety-gap commits

This is a source/document review only. It does not claim a fresh Windows, LM Studio, Spotify, or Siri runtime acceptance run.

## Gate decision

### Production Local AI fallback / executable promotion: **NO-GO**

Do not enable production `fallback`, do not set `LOCAL_AI_FALLBACK_APPROVED=true` as a production acceptance action, and do not claim V1 Local AI production authorization yet.

### Shadow-only hardening, evidence collection, and blocker remediation: **GO**

Work may continue only where model output cannot execute: documentation reconciliation, benchmark evidence, unit/security tests, production-aligned loopback shadow validation, and narrowing/hardening of the existing guarded path.

## Positive findings

The current implementation has a strong fail-closed shape:

1. The runtime defaults to `LOCAL_AI_ENABLED=false` / `LOCAL_AI_MODE=off`.
2. `shadow` never returns an executable action.
3. `fallback` is separately gated by `LOCAL_AI_FALLBACK_APPROVED`.
4. The first production-facing AI schema is narrowed to `spotify_play_track` / `unknown`; extra fields are forbidden.
5. LM Studio transport is restricted to unauthenticated `http://127.0.0.1:<port>/v1`, rejects redirects/credentials/query/fragment, bounds input/output, uses a timeout, and permits only one in-flight inference.
6. A deterministic eligibility gate runs before inference.
7. Requests carrying `clarification_token` bypass AI and remain server-owned/deterministic.
8. Hostile authority strings and unresolved-reference cases are rejected before model use.
9. AI slots are deterministically grounded back to the original utterance; an ungrounded track rejects the interpretation and ungrounded optional artist/album fields are discarded.
10. Only the policy gate creates a `ValidatedAction`; AI cannot create Spotify IDs/URIs, executable paths, commands, URLs, process IDs, or trusted catalog objects.
11. Recent tests cover strict schema rejection, grounding, hostile input, loopback enforcement, single-flight transport, shadow non-execution, promotion gating, transport fail-closed behavior, and clarification bypass.
12. The revised benchmark recorded `0%` false execution, `0%` post-grounding false acceptance, `100%` deterministic-only safe-unknown, `100%` safety-only safe-unknown, `95.24%` supported semantic accuracy, and sub-2-second P95 for the currently evaluated Qwen2.5 Coder model.

## Blocking findings

### B1 — Authority-chain conflict blocks production authorization

**Severity: BLOCKER**

`AGENTS.md` states that `docs/SOURCE_SPEC.md` is the final arbiter when documents conflict.

But `docs/SOURCE_SPEC.md` §94 explicitly says V1 should not use Local LLM, and §95 says LLM command understanding is future extensibility and "現在不要實作".

Newer `docs/SPEC.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, and `PROJECT_STATUS.md` describe a later product decision allowing guarded Local AI in V1.

Because the repository's own source-of-truth rule gives `SOURCE_SPEC.md` precedence, the later documents cannot by themselves authorize production Local AI.

**Required resolution:** an explicit user-approved governance/spec migration must state which later decision supersedes SOURCE_SPEC §94/§95 while keeping the historical source document read-only. Update the source-of-truth/migration documentation so future agents cannot interpret both rules as simultaneously authoritative.

### B2 — No production AI runtime acceptance

**Severity: BLOCKER for fallback promotion**

The current evidence is shadow/offline benchmark evidence. The repository itself still records that Local AI production Windows/Spotify/Siri acceptance and fallback promotion are not complete.

Before executable fallback promotion, run production-aligned acceptance with:

- same-host LM Studio bound to loopback
- the exact model/configuration being proposed
- current production eligibility/schema/grounding/policy code
- real Windows Agent process
- real Spotify resolution/playback path for approved safe cases
- fail-closed cases for hostile input, unresolved references, malformed model output, timeout, busy transport, and unavailable LM Studio
- confirmation that deterministic commands and clarification behavior are unchanged

Do not convert source/unit/shadow evidence into a real-world acceptance claim.

### B3 — Architecture proposal contains stale broader AI authority

**Severity: HIGH documentation risk**

`docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` still describes a broader initial AI allowlist including playback controls and `select_candidate`, and describes clarification replies entering Local AI.

The current implementation and current architecture/security documents deliberately narrowed the production-facing AI contract to `spotify_play_track` / `unknown`, with clarification and playback controls deterministic-only.

This stale proposal can cause a future coding agent to re-expand AI authority accidentally.

**Required resolution:** mark the broader sections as superseded or rewrite them to the current guarded semantic-retry scope before any new AI implementation slice.

### B4 — Promotion evidence is not durable enough for an auditable production decision

**Severity: HIGH process/reproducibility risk**

The latest benchmark aggregates are recorded in project status, while full run artifacts live under ignored `runtime/ai_poc/`.

For production promotion, keep a sanitized committed evidence summary containing at minimum:

- reviewed git commit SHA
- fixture SHA/hash and case counts by scope
- exact LM Studio version
- exact model identifier and quantization
- prompt/schema version or hash
- runtime endpoint mode (loopback)
- completion-token/timeout settings
- aggregate safety and quality metrics
- known failure cases
- explicit statement that no secrets/raw tokens are included

This does not require committing large CSV/JSONL runtime outputs.

## Non-blocking observations

- The local boolean promotion gate is acceptable only as a trusted local operator control; it is not itself proof that a model/configuration passed review.
- The three remaining supported benchmark failures are album/artist role mistakes. Current deterministic grounding limits authority, but these should remain in the regression corpus and be retested after prompt/grounder changes.
- The implementation correctly keeps AI behind the existing trusted Spotify resolver, so model mistakes should remain semantic/search mistakes rather than execution-authority mistakes as long as the current boundary is preserved.

## Required sequence before production fallback can be reconsidered

1. Resolve B1 with an explicit authoritative product/spec decision.
2. Reconcile the stale architecture proposal in B3.
3. Commit sanitized benchmark/promotion evidence per B4.
4. Re-run the complete source/security test suite at the exact candidate commit.
5. Perform production-aligned loopback shadow acceptance on Windows.
6. Run a separate promotion review against the exact model/configuration/commit.
7. Only after all above gates pass may fallback execution be considered.

## Reviewer conclusion

**Do not start production Local AI fallback work yet.**

**Start blocker-removal and shadow-only validation work now.**

The implemented security shape is suitable for continued guarded evaluation, but the repository is not yet in a state where executable Local AI fallback should be treated as authorized or accepted.
