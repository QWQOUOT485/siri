# Local AI Independent Promotion Review — 2026-09-20

## Review decision

**Production Local AI fallback: NO-GO.**

This is a new review of the current evidence, not a carry-forward of the
2026-09-19 review. It does not select a model and does not authorize changing
`LOCAL_AI_FALLBACK_APPROVED`.

Required runtime state remains:

```text
LOCAL_AI_MODE=off or shadow
LOCAL_AI_FALLBACK_APPROVED=false
```

## Exact scope reviewed

- Benchmark/review baseline at run start: `f1038bab2d56093a2a78f693a4cc89e8cb6c5cbc`
- Benchmark evidence: `docs/LOCAL_AI_BENCHMARK_2026-09-20.md`
- Windows shadow evidence: `docs/LOCAL_AI_SHADOW_ACCEPTANCE_2026-09-20.md`
- Production endpoint observed: same-host `127.0.0.1` LM Studio
- LM Studio: ProductVersion `0.4.20.0`, FileVersion `0.4.20+1`, CLI commit `71bd99c`
- Candidate configuration observed on the running Agent: `qwen2.5-coder-1.5b-instruct`,
  Q4_K_M, temperature `0`, max completion tokens `256`, Agent timeout `2s`,
  bounded response `32768`, shadow mode
- Current working tree also contains unrelated Spotify personalization source
  and semantic-memory changes. They were preserved and are not treated as
  Local AI promotion evidence.
- The live shadow run predates those later semantic-memory commits; their
  changed runtime/config files were not deployed or accepted in that run.

## Evidence accepted for this review

- Fixed 109-case benchmark rows are complete for all three model candidates and
  both prompt/schema modes. The benchmark records row-level source commits and
  keeps raw output ignored.
- `qwen3.5-0.8b` produced no usable JSON; `qwen3-4b` strict-schema mode
  completed but reached only 28.57% supported semantic accuracy and 16.67%
  semantic-retry accuracy. These are quality failures, not model approvals.
- `qwen2.5-coder-1.5b-instruct` reached 95.24% supported semantic accuracy,
  100% semantic-retry accuracy, 100% deterministic-only safe-unknown,
  100% safety-only safe-unknown, 0% observed false execution, and 0% observed
  post-grounding false acceptance in the fixed corpus.
- Real Windows Agent probes confirmed loopback/shadow behavior for resolver
  retry, parser miss, hostile input, shutdown confirmation, and server-owned
  clarification. AI output did not form an executable action in shadow mode.
- Current-tree source snapshot evidence: `224 passed`, compileall passed,
  `pip check` passed, and `git diff --check` passed; only the two existing
  dependency deprecation warnings remain. This later-tree result does not
  replace an exact promotion-commit run.

## Blocking findings

### B1 — Production-aligned fail-closed matrix is incomplete

Malformed output, timeout, single-flight busy, oversized response, ungrounded
track, and invented optional-slot cases have source/unit evidence. The attempted
isolated live fault-injection harness was blocked before process start, so these
rows are not real-Agent live transport evidence. Promotion requires either a
safe repeatable live fault-injection method or an explicitly accepted review
decision that source evidence is sufficient for each failure class.

### B2 — Real Siri voice and real-account acceptance is incomplete

The run exercised the deployed Windows Agent over authenticated loopback HTTP
and used the real Spotify path for safe bounded probes. It did not complete a
fresh Siri voice flow with the exact candidate configuration, and it does not
replace the separate real-account/Shortcut acceptance boundary.

### B3 — No exact-candidate promotion authorization exists

The benchmark evidence is complete and preserves row provenance, but the rows
were produced across the previous source commit `aecc6dd` and the current
documentation-only commit `f1038ba`. The fixture and benchmark script were
unchanged, which preserves comparability, but this is still evidence rather
than an independent authorization for executable fallback.

### B4 — The 4B candidate fails the quality gate

`qwen3-4b` does not meet the initial semantic or latency-quality target in
either mode. Structured output did not repair the failure. It must not be
promoted or used as a basis for broadening the AI contract.

## Safety conclusion

No observed false execution or post-grounding false acceptance occurred in the
fixed benchmark, and the live Agent preserved the deterministic/shadow boundary
for the tested cases. That positive evidence is bounded: it does not waive the
missing live fault matrix, Siri/real-account acceptance, or a future review of
the exact executable-fallback configuration.

## Required next actions before reconsideration

1. Keep the runtime `off` or `shadow` and preserve the narrow
   `spotify_play_track` / `unknown` schema.
2. Complete a reproducible production-aligned fail-closed test for the listed
   transport and grounding failures without changing production `.env`.
3. Complete fresh Windows Agent + safe Spotify + Siri/Shortcut acceptance for
   the exact candidate configuration under review.
4. Re-run the final source/security/regression suite at the exact promotion
   commit and verify the sanitized evidence hashes.
5. Obtain a separate independent review after those gates; only that review
   may reconsider executable fallback.
