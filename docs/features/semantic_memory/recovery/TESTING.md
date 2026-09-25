# Testing and Acceptance

## Top five rollout blockers

These tests must pass before Phase 1 can be enabled:

1. **Client cannot supply `provider_entity_id` to MemoryLearner.**
2. **A conflicted alias never auto-selects either mapping.**
3. **AI/fuzzy/vector evidence cannot promote an alias to `confirmed`.**
4. **`SASIOVERLXRD ↔ Sad overlxrd` end-to-end regression succeeds safely.**
5. **Concurrent writes cannot leave RAM index and SQLite silently diverged.**

## SASIOVERLXRD acceptance scenario

First occurrence:

```text
user intent:
play 死亡是生命的終點 by SASIOVERLXRD

Siri/ASR artist:
Sad overlxrd

no confirmed alias
→ candidate recovery
→ trusted clarification
→ user selects SASIOVERLXRD
→ playback succeeds
→ MemoryLearner confirms alias
```

Second occurrence:

```text
Sad overlxrd
→ exact confirmed RAM alias
→ canonical SASIOVERLXRD
→ normal Spotify resolver
```

Expected:

- no AI required
- no fuzzy scan required for the exact alias
- no client-supplied Spotify identity
- normal Spotify ambiguity and Live rules remain active

## Unit tests

At minimum:

- deterministic normalization
- Unicode/case/space/punctuation variants
- Traditional/Simplified behavior
- legitimate short/one-character entity support
- confirmed exact alias hit
- provisional alias cannot rewrite
- conflicted alias cannot rewrite
- disabled alias ignored
- idempotent entity/alias writes
- bounded text inputs
- invalid trust-state transitions rejected
- provider entity ID cannot originate from client input
- MemoryLearner requires authoritative event
- playback failure prevents confirmation
- AI cannot confirm
- fuzzy cannot confirm
- future vector path cannot confirm
- DB unavailable -> safe deterministic fallback
- migration/version behavior
- observations default off

## Concurrency tests

Test:

```text
two confirmations: same alias, same entity
two confirmations: same alias, different entity
read during write
SQLite busy/locked
process restart after DB commit
RAM rebuild after simulated RAM update failure
```

Different entity confirmations must produce conflict, not last-write-wins.

## Security tests

Verify:

- alias text cannot become shell/CMD/PowerShell
- alias text cannot become executable/filesystem path
- alias text cannot become arbitrary URL
- client cannot supply trusted provider identity
- request cannot set trust state
- request cannot set DB path
- clarification token cannot mutate an arbitrary alias
- oversized/control-character inputs are safely rejected/normalized
- non-Spotify actions bypass this layer
- shutdown/force-close/firewall bypass this layer
- corrupt DB does not weaken policy
- Spotify catalog content is not sent to embedding/AI memory path

## Fuzzy auto-retry gate

Phase 1 automatic fuzzy rewrite is disabled.

A future code path may be considered only after a fixed adversarial corpus demonstrates:

```text
0 wrong automatic canonicalizations
```

This gate must be wired to the code feature flag.

## Fixture categories

Create a fixed fixture such as:

```text
tests/fixtures/asr_entity_recovery_cases.json
```

Include:

- stylized Latin artist names
- `SASIOVERLXRD / Sad overlxrd / sasiover lord / sassy overlord`
- spacing/punctuation/case variants
- Traditional/Simplified variants
- short names
- same-name artists
- same-title tracks
- near-spelling but different real artists
- wrong fuzzy leader
- alias conflicts
- AI hallucinated artist
- poisoning attempts
- concurrent confirmations

## Performance benchmark

Measure on the actual Windows deployment host at:

```text
100 aliases
1,000 aliases
10,000 aliases
50,000 aliases
```

Record:

- startup index load
- normalization P50/P95
- exact alias lookup P50/P95
- RapidFuzz retrieval P50/P95
- full local recovery P50/P95
- SQLite size
- RAM usage

Design targets, not pre-verified facts:

```text
confirmed alias lookup: P95 < 5 ms
non-vector local recovery: P95 < 30 ms
```

Do not block Phase 1 on FTS5/vector benchmarks because they are out of scope.

## Source verification before merge

Run at least:

```text
pytest -q
python -m compileall app tests
pip check
git diff --check
```

Do not delete security tests to make the suite pass.

## Runtime acceptance

Before enabling memory on the installed Agent:

- create DB successfully on Windows
- restart and reload confirmed alias
- verify DB -> RAM rebuild
- run the first/second `Sad overlxrd` scenario
- verify existing Spotify clarification on iPhone remains unchanged
- verify no regression in `播放死亡是生命的終點`
- measure fast-path latency
