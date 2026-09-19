# Phase 1 Implementation Plan

Status: **approved to implement**.

The first implementation intentionally excludes vector memory and automatic fuzzy canonicalization.

## Slice 1 — Domain models

Create:

```text
app/domain/semantic_memory.py
```

Suggested models/enums:

- `AliasTrustState`
- `SemanticEntity`
- `AliasRecord`
- `NormalizedEntityText`
- `AliasCandidate`
- `RecoveryCandidateEvidence`

Requirements:

- bounded strings
- no arbitrary command/path/URL/URI execution fields
- clear separation between local DB identity and Spotify provider identity

## Slice 2 — SQLite infrastructure

Create:

```text
app/infrastructure/semantic_memory_db.py
```

Implement schema v1:

- `entities`
- `aliases` with reserved `scope_context`
- optional `alias_observations`

Requirements:

- foreign keys
- explicit transactions
- migration/version handling
- bounded busy timeout
- fail safely on unavailable/corrupt DB
- observations disabled by default

The database lives under ignored runtime state.

## Slice 3 — EntityNormalizer

Create:

```text
app/services/entity_normalizer.py
```

Produce non-destructive normalized forms using project-standard Chinese normalization plus Unicode/case/whitespace/punctuation handling.

Do not add a blanket two-character minimum.

## Slice 4 — AliasMemory

Create:

```text
app/services/alias_memory.py
```

Responsibilities:

- load confirmed active non-conflicted aliases into RAM
- exact lookup
- RapidFuzz top-k candidate-only lookup
- conflict/read helpers
- rebuild RAM index from DB

It does not promote aliases to confirmed.

## Slice 5 — MemoryLearner

Create:

```text
app/services/memory_learner.py
```

This is the only automatic trust-promotion authority.

Phase 1 automatic confirmation requires:

```text
trusted clarification candidate selected
AND playback succeeded
```

Different trusted entities confirmed for the same alias must produce `conflicted`, not last-write-wins.

## Slice 6 — EntityRecoveryService

Create:

```text
app/services/entity_recovery.py
```

Responsibilities:

- compose normalization + memory lookup + candidate evidence
- exact confirmed alias may canonicalize
- RapidFuzz remains candidate-only
- no playback
- no Spotify URI/ID selection
- no trust promotion

Track-first evidence can be added in Phase 1B after the core memory path is accepted.

## Slice 7 — Runtime/config wiring

Suggested initial config:

```env
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_SEMANTIC_MEMORY_PATH=runtime/semantic_memory/semantic_memory.sqlite3
LOCAL_SEMANTIC_MEMORY_OBSERVATIONS_ENABLED=false
LOCAL_SEMANTIC_MEMORY_MAX_ALIASES=1000
LOCAL_SEMANTIC_MEMORY_MAX_OBSERVATIONS=1000
LOCAL_SEMANTIC_MEMORY_FUZZY_AUTO_RETRY=false
```

Rules:

- memory is optional
- Agent startup must survive memory being disabled/unavailable
- fuzzy auto-retry remains false
- no new client request fields for memory authority

## Slice 8 — Spotify/clarification integration

Integrate without replacing existing authority:

```text
parser
→ exact confirmed alias recovery
→ existing Spotify resolver
→ unresolved fuzzy candidates
→ existing Spotify clarification store
→ selected trusted candidate
→ playback
→ MemoryLearner confirm event
```

Do not create a new clarification token/store.

## Slice 9 — Metrics

Bounded counters/timers:

```text
semantic_memory_exact_hit
semantic_memory_fuzzy_candidate
semantic_memory_conflict
semantic_memory_confirmed_write
semantic_memory_provisional_write
recovery_clarification
normalization_ms
alias_lookup_ms
fuzzy_ms
total_command_ms
```

No secrets.

## Slice 10 — Acceptance/deployment

Before runtime enable:

1. full source tests pass
2. Windows DB creation/migration verified
3. restart persistence verified
4. RAM rebuild verified
5. first-run `Sad overlxrd` requires safe recovery/clarification
6. trusted selection + playback success confirms alias
7. second-run exact alias resolves without AI/fuzzy
8. existing Spotify resolver/Live filtering unchanged
9. existing Siri clarification E2E unchanged
10. on-host latency measured

Only after acceptance should `LOCAL_SEMANTIC_MEMORY_ENABLED` be enabled for the installed Agent.

## Deferred roadmap

### Phase 1B

Track-first Spotify evidence, still candidate-only.

### Phase 2

SQLite FTS5 trigram only if measured RapidFuzz full-scan latency justifies it.

### Phase 3

User-utterance semantic vector retrieval in shadow mode only.

### Phase 4

Vector evidence may influence candidate retrieval if shadow metrics justify it; never direct playback.

### Phase 5

Combine memory with Local AI semantic retry only after the independent Local AI promotion gate passes.

## Explicitly removed

Do not implement a Soundex/Metaphone/G2P text-derived phonetic-key roadmap for stylized artist names. Confirmed real Siri misrecognitions are the preferred practical phonetic memory.
