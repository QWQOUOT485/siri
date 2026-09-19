# Semantic Memory Phase 1 — Real Spotify Follow-up Acceptance

Date: 2026-09-20

Decision: **PARTIAL ACCEPTANCE / NO-GO FOR ENABLEMENT**

This is a follow-up to
[`SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md`](SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md).
It records the real Spotify evidence obtained from the current source in an
isolated staged runtime. The installed Agent was not overwritten, and the
production semantic-memory flag remains disabled.

## Acceptance matrix

| Check | Result | Boundary |
| --- | --- | --- |
| Spotify access-token refresh | **PASS** | Existing local token store; token value not logged |
| Canonical trusted Spotify search | **PASS** | Real account, read-only search |
| ASR alias directly produces candidates | **BLOCKED** | `SPOTIFY_TRACK_NOT_FOUND` |
| Real playback through server-owned clarification | **PASS, partial** | Candidate was seeded from canonical trusted search |
| MemoryLearner confirmation after real playback | **PASS, partial** | Existing clarification store and real playback |
| Restart and second exact alias hit | **PASS, partial** | Current source staged runtime; exact hit 1, fuzzy 0 |
| Installed Agent runtime | **NOT ACCEPTED** | Installed copy still lacks Semantic Memory |
| iPhone/Siri voice E2E | **NOT RUN** | Requires an updated installed runtime |
| Production enablement | **NO-GO** | Normal first-occurrence candidate path remains open |

## Real Spotify observations

The existing local Spotify token was expired at the start of the probe. The
Agent's existing refresh path succeeded without exposing the token. The
refreshed token retained the playback scopes used by this test, but it did not
include `user-read-recently-played`; that unrelated personalization gate
remains pending.

A read-only search confirmed that the account has the trusted artist
`SASIOVERLXRD` and that the account's actual track title is
`死亡不是生命的終點`. The earlier documented example
`死亡是生命的終點` does not resolve in this account.

The normal first-occurrence request using artist text `Sad overlxrd` returned
`SPOTIFY_TRACK_NOT_FOUND` and produced no clarification candidates, even when
the account's actual track title was used. This is the current blocker: the
resolver does not yet create a trusted candidate from this ASR alias. The
result was not converted into a pass by selecting a client-supplied identity.

For a bounded partial acceptance, the current source performed a canonical,
server-side trusted search for the real track, inserted that trusted result
into the existing server-owned clarification store with the observed alias,
and selected it through the normal opaque-token selection method. Real Spotify
playback succeeded and `MemoryLearner` confirmed `Sad overlxrd` → `SASIOVERLXRD`.

After closing and rebuilding the staged runtime, the same alias request
successfully played the track again. The exact-memory counter increased by one
and the fuzzy-candidate counter did not increase. This proves the real
playback/write/restart/exact-hit portion, but it does **not** prove the missing
ASR-alias candidate-recovery portion or Siri voice behavior.

## Windows performance on the staged current source

Measured on the Windows host with the real confirmed alias and a 1,000-sample
loop for each operation:

| Measurement | P50 | P95 | Notes |
| --- | ---: | ---: | --- |
| Runtime build + index load | — | — | 70.0876 ms total startup sample |
| Normalization | 0.0163 ms | 0.0175 ms | 1,000 samples |
| Exact alias lookup | 0.0170 ms | 0.0186 ms | 1,000 samples |
| Fuzzy candidate lookup | 0.0213 ms | 0.0234 ms | Candidate-only |
| Full local recovery | 0.0240 ms | 0.0259 ms | Unresolved near-alias query |

The temporary SQLite file was 40,960 bytes. Process RSS was approximately
49,651,712 bytes before runtime construction and 56,209,408 bytes after it;
the 6,557,696-byte delta is an approximate process delta, not an isolated
semantic-index allocation measurement.

## Remaining gate

Do not enable `LOCAL_SEMANTIC_MEMORY_ENABLED`. The smallest next technical
decision is to either provide a real account/query where the existing
deterministic resolver returns the intended trusted ambiguity candidates, or
open a separately reviewed candidate-recovery/track-first slice. Directly
seeding a candidate is useful evidence for the learner and playback path, but
must not be treated as a replacement for that missing first-occurrence path.

No production database, Spotify token, API key, clarification token, or raw
runtime log was committed.
