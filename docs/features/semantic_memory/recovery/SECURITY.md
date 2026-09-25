# Semantic Recovery Security Boundaries

## Authority model

The new memory layer must not widen the project's execution authority.

```text
untrusted Siri text
→ deterministic interpretation/recovery
→ trusted Spotify response
→ trusted SpotifyTrackRef
→ adapter
```

Memory, fuzzy matching, vector similarity and AI are interpretation aids only.

## Phase 1 automatic authority

The only semantic-memory auto-rewrite allowed is:

```text
exact normalized alias
AND confirmed
AND active
AND non-conflicted
```

Everything else is candidate-only.

## Provider identity

Client requests must not contain or control:

- `provider_entity_id`
- trusted entity primary keys
- memory trust state
- canonical Spotify URI
- canonical Spotify track ID

Provider IDs stored in semantic memory must originate from server-side validated Spotify responses.

## Memory poisoning defenses

1. AI cannot confirm memory.
2. Fuzzy retrieval cannot confirm memory.
3. Future vector retrieval cannot confirm memory.
4. Popularity cannot confirm memory.
5. Personalization signals cannot confirm memory.
6. One automatic playback result cannot confirm memory.
7. Trusted clarification selection plus playback success is required for automatic confirmation.
8. A conflicted alias leaves the automatic fast path.
9. Client input cannot supply the trusted provider target.
10. Memory failure cannot reduce Spotify resolver/clarification checks.
11. Memory fields do not include arbitrary shell command/path/URL execution authority.
12. High-risk/system commands cannot enter this recovery layer.

## Fuzzy automatic retry gate

Phase 1 must keep fuzzy/track-first automatic canonicalization disabled.

If a later implementation proposes it, code must have an explicit gate, e.g.:

```text
LOCAL_SEMANTIC_MEMORY_FUZZY_AUTO_RETRY=false
```

Promotion requires a fixed adversarial corpus with:

```text
0 observed wrong automatic canonicalizations
```

The gate must exist in code, not only documentation.

## Spotify content and AI/ML

Under the current Spotify API policy note, do not ingest Spotify catalog content into AI/ML models.

Therefore do not send Spotify-derived artist/track/album/catalog metadata to:

- Local AI prompts for memory resolution
- embedding models
- semantic vector indexes

A future vector-memory feature may embed user-authored/Siri-transcribed utterances only, and must be rechecked against then-current Spotify policy before release.

Deterministic use of validated Spotify metadata for matching, identity, ranking and clarification remains separate.

## Privacy defaults

Recommended initial defaults:

```text
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_SEMANTIC_MEMORY_OBSERVATIONS_ENABLED=false
LOCAL_SEMANTIC_MEMORY_FUZZY_AUTO_RETRY=false
```

Observation logging must not silently create a long-lived behavioral history.

Logs must not contain API keys, OAuth tokens, clarification tokens or arbitrary Spotify URIs.

Raw utterance diagnostics should follow existing privacy/logging policy and default to disabled/redacted where practical.

## Failure behavior

### DB unavailable/corrupt

```text
disable semantic memory
→ preserve existing deterministic Spotify behavior
```

Do not block Agent startup solely because optional semantic memory is unavailable.

### Fuzzy/vector subsystem failure

Skip that recovery layer.

### AI failure

Use the existing fail-closed Local AI behavior.

### Spotify unavailable

Return the normal Spotify failure. Memory cannot fabricate an offline trusted track.

## High-risk exclusions

The semantic recovery layer never handles:

- shutdown
- shutdown confirmation
- force-close
- firewall mutation/administration
- arbitrary shell/CMD/PowerShell
- arbitrary executable path
- arbitrary URL
- generic process IDs
- app/system administration

## Clarification integrity

Reuse the existing server-owned Spotify clarification mechanism. Recovery evidence may help produce candidates but cannot let the client create or alter trusted candidate IDs.

## Database path/config

The request body must not control the database path, schema, trust state, or provider identity.

Migrations must fail safely; a migration error disables memory rather than silently rebuilding trust data with guessed mappings.
