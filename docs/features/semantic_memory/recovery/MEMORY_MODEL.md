# Alias Memory Model and Storage

## Trust states

The authoritative Phase 1 states are:

```text
observation
provisional
confirmed
conflicted
disabled
```

### observation

Diagnostic evidence only. It cannot rewrite a request.

Persistent observation logging is disabled by default.

### provisional

Stronger evidence than an observation, but still non-authoritative.

It can influence candidate evidence/clarification only.

### confirmed

The only Phase 1 state that may participate in exact automatic canonicalization.

Automatic promotion requires:

```text
trusted clarification selection
AND playback success
```

### conflicted

The same normalized alias has credible mappings to more than one entity.

A conflicted alias is removed from the confirmed fast path and requires context/clarification.

Never use latest-write-wins, popularity-wins, most-played-wins, or recent-wins to resolve a conflict automatically.

### disabled

Explicitly quarantined or manually disabled. It is ignored for automatic behavior.

## Single write authority

`MemoryLearner` is the only automatic trust-state promotion authority.

The following may never directly promote to `confirmed`:

- AI
- RapidFuzz
- vector retrieval
- Spotify popularity
- saved/liked status
- Top Artists/Tracks
- Recently Played
- one automatic playback result

## Storage

Recommended local database:

```text
runtime/semantic_memory/semantic_memory.sqlite3
```

Requirements:

- gitignored
- schema-versioned
- local-user storage
- bounded inputs and optional diagnostic retention
- database failure disables memory rather than lowering safety

## Table: entities

```sql
CREATE TABLE entities (
    entity_pk              INTEGER PRIMARY KEY,
    entity_type            TEXT NOT NULL,
    provider               TEXT NOT NULL,
    provider_entity_id     TEXT NOT NULL,
    canonical_name         TEXT NOT NULL,
    normalized_name        TEXT NOT NULL,
    created_at             INTEGER NOT NULL,
    last_seen_at           INTEGER NOT NULL,
    active                 INTEGER NOT NULL,
    UNIQUE(provider, entity_type, provider_entity_id)
);
```

Rules:

- `provider_entity_id` originates from a trusted Spotify response.
- client input cannot create a trusted entity row directly.
- storing a provider ID locally does not grant client authority over it.

## Table: aliases

```sql
CREATE TABLE aliases (
    alias_pk               INTEGER PRIMARY KEY,
    entity_pk              INTEGER NOT NULL,
    raw_alias              TEXT NOT NULL,
    normalized_alias       TEXT NOT NULL,
    compact_alias          TEXT NOT NULL,
    trust_state            TEXT NOT NULL,
    source                 TEXT NOT NULL,
    scope_context          TEXT NULL,
    confirmation_count     INTEGER NOT NULL DEFAULT 0,
    success_count          INTEGER NOT NULL DEFAULT 0,
    failure_count          INTEGER NOT NULL DEFAULT 0,
    created_at             INTEGER NOT NULL,
    last_used_at           INTEGER NULL,
    disabled_at            INTEGER NULL,
    FOREIGN KEY(entity_pk) REFERENCES entities(entity_pk)
);
```

`scope_context` is reserved now but unused in Phase 1. Future context-specific aliases require a separate reviewed design before this field may influence execution.

## Optional table: alias_observations

Observation logging is **OFF by default**.

```sql
CREATE TABLE alias_observations (
    observation_pk         INTEGER PRIMARY KEY,
    normalized_alias       TEXT NOT NULL,
    entity_pk              INTEGER NULL,
    evidence_type          TEXT NOT NULL,
    outcome                TEXT NOT NULL,
    created_at             INTEGER NOT NULL
);
```

Recommended config:

```text
LOCAL_SEMANTIC_MEMORY_OBSERVATIONS_ENABLED=false
```

If enabled, use bounded retention and a clear/reset command.

## Future table: utterance_memories

Not Phase 1.

If semantic vector memory is later measured to add value, use user-authored/Siri-transcribed utterances only. Prefer bounded retention and reassess whether raw normalized text is necessary or whether hashes/features are sufficient.

## RAM index

SQLite is the persistent source of truth.

At startup:

```text
SQLite confirmed + active + non-conflicted aliases
→ build RAM dictionary/index
```

Normal exact lookup does not need a disk read.

## Update ordering

For a trust-changing write:

```text
BEGIN
write SQLite
COMMIT
update/swap RAM index
```

If RAM update fails after commit, rebuild the RAM index from SQLite.

Do not update RAM first.

## Concurrency assumption

Phase 1 assumes:

```text
one Windows Agent process
one semantic-memory SQLite database
multiple concurrent API requests are possible
```

Concurrent confirmations must not produce silent last-write-wins behavior.

If two trusted confirmations map one alias to different entities, transition to `conflicted`.

A future multi-process/shared-database architecture requires a new concurrency review.

## Retention

Confirmed aliases do not need an aggressive TTL. Expiry should be evidence-driven:

- repeated contradiction
- provider entity invalidation
- manual disable/removal

Provisional/diagnostic rows may use time/row-count retention.

## Reset/manage operations

A future authenticated local CLI may provide:

```text
status
list confirmed aliases
list conflicts
disable alias
remove alias
clear provisional
clear observations
clear all semantic memory
rebuild RAM index
```

Do not expose an unauthenticated LAN mutation API.
