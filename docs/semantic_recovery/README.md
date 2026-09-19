# Local Semantic Recovery

Status: **Phase 1 approved for implementation** (2026-09-19).

This directory is the authoritative implementation specification for local ASR/entity recovery and alias memory.

The motivating cases are:

```text
spoken artist: SASIOVERLXRD
Siri/ASR text: Sad overlxrd
```

and parser/resolver disagreement such as:

```text
播放死亡是生命的終點
```

where deterministic grammar can produce a syntactically valid but semantically wrong artist/track split.

## Core rule

Only an **exact, confirmed, non-conflicted alias** may automatically canonicalize an entity in Phase 1.

These signals are **candidate/evidence only** and may not silently rewrite user intent:

- RapidFuzz / edit similarity
- track-first recovery
- future vector retrieval
- Local AI output

They may help build a clarification candidate set, but they do not select a Spotify ID/URI and do not execute playback.

## Authority chain

```text
Siri / ASR text
→ deterministic parser
→ entity normalization
→ exact confirmed alias memory
→ deterministic Spotify resolver
→ fuzzy / track-first evidence when unresolved
→ deterministic clarification when useful
→ optional future vector evidence
→ Local AI semantic retry only when eligible
→ strict schema
→ deterministic grounding
→ AIPolicyGate
→ deterministic Spotify resolver
→ trusted SpotifyTrackRef
→ playback
```

The existing Spotify resolver and clarification store remain authoritative.

## Phase 1 scope

Implement:

- `EntityNormalizer`
- local SQLite persistence
- five-state alias trust model
- RAM index containing confirmed active aliases only
- RapidFuzz top-k retrieval in **candidate-only** mode
- `MemoryLearner` as the single trust-promotion authority
- confirmation only after trusted clarification selection **and successful playback**
- conflict handling
- bounded metrics and management/reset behavior
- security, concurrency, persistence and latency tests
- fixed `SASIOVERLXRD ↔ Sad overlxrd` regression

Do not implement in Phase 1:

- semantic vector memory
- ANN/vector database
- Soundex/Metaphone/G2P phonetic keys
- fuzzy automatic canonicalization
- track-first automatic canonicalization
- AI-confirmed aliases
- new clarification token system

## Documents

- [Recovery pipeline](RECOVERY_PIPELINE.md)
- [Memory model and storage](MEMORY_MODEL.md)
- [Security boundaries](SECURITY.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Testing and acceptance](TESTING.md)
- [Research and references](REFERENCES.md)

## Non-negotiable invariants

1. Memory is not execution authority.
2. AI is not execution authority.
3. Fuzzy similarity is not identity.
4. Vector similarity is not identity.
5. Spotify IDs/URIs used for playback originate only from trusted Spotify responses.
6. Conflict reduces authority; it never raises confidence.
7. Genuine ambiguity continues to use deterministic clarification.
8. High-risk/system actions never enter this recovery layer.
9. Memory failure must not break existing deterministic commands.
10. Phase 1 automatic canonicalization is limited to exact confirmed aliases.
