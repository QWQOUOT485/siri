
# Candidate Recovery / Phase 1B

Status: **Phase 1B explicitly scheduled; source implementation is in progress on the dedicated branch. Runtime acceptance is not yet proven.**

This document records the product/retrieval scope now being implemented after
the v1.0 acceptance handoff. Installed/runtime acceptance remains a separate
gate and is not implied by source or unit evidence.

It does not change the current production authority model and does not authorize
new automatic playback behavior.

---

## 1. Problem

The current clarification path can only present candidates that already exist
inside the bounded trusted Spotify result set.

That means the system can still fail even when the desired track exists in
Spotify.

Example:

~~~
User:
"I want to listen to Stay"

Initial trusted clarification candidates:
1. wrong STAY
2. wrong STAY
3. wrong STAY

Desired track:
STAY — The Kid LAROI, Justin Bieber
~~~

If the desired track is not present in the first bounded candidate set, the
current clarification UI has nothing safe for the user to select.

Memory cannot solve this first occurrence because the correct trusted entity
has not yet been selected and confirmed.

---

## 2. Related ASR / alias problem

The same underlying retrieval gap appears in the existing Semantic Memory case:

~~~
spoken / ASR text:
Sad overlxrd

desired trusted artist:
SASIOVERLXRD
~~~

Current observed blocker:

~~~
Sad overlxrd
→ normal resolver
→ SPOTIFY_TRACK_NOT_FOUND
→ no clarification candidates
~~~

The later memory path already works once a trusted candidate is available:

~~~
trusted candidate
→ explicit clarification selection
→ successful playback
→ MemoryLearner
→ SQLite confirmed alias
→ restart
→ exact RAM alias hit
~~~

Therefore Phase 1B should focus on **trusted candidate recovery before
clarification**, not on weakening MemoryLearner.

---

## 3. Desired behavior

When the first trusted candidate page does not contain the intended result, the
Agent should be able to perform a second bounded retrieval step.

Conceptually:

~~~
initial deterministic Spotify search
→ bounded trusted candidate set
→ user says "none of these" / equivalent
→ bounded candidate recovery
→ next trusted candidate set
→ clarification
→ explicit user selection
→ playback
→ optional trusted memory learning
~~~

The second retrieval must still use Spotify/server-owned identities.

---

## 4. Example: STAY

Target scenario:

~~~
User:
"播放 Stay"

Agent returns up to 3 trusted candidates.

User:
"都不是"
or another reviewed equivalent.

Agent:
performs bounded title-first candidate recovery

Internal search pool may be larger than 3
but remains bounded.

Example:
up to 10–20 trusted Spotify search results
→ exact/normalized title filtering
→ Live/Concert exclusion
→ deterministic ranking
→ remove already presented candidates
→ return next maximum 3 clarification candidates

Desired result eventually appears:
STAY — The Kid LAROI, Justin Bieber

User selects it.
→ trusted playback
~~~

Do **not** make Siri read 10–20 candidates.

The large pool is internal only; public clarification remains bounded.

---

## 5. Example: Sad overlxrd

Target first-occurrence flow:

~~~
User:
"播放死亡不是生命的終點，Sad overlxrd"

normal deterministic resolver misses
→ candidate recovery becomes eligible
→ trusted Spotify evidence finds SASIOVERLXRD candidate
→ clarification presents bounded trusted candidates
→ user explicitly selects
→ playback succeeds
→ MemoryLearner confirms:

Sad overlxrd
→ SASIOVERLXRD
~~~

Second occurrence:

~~~
Sad overlxrd
→ exact confirmed RAM alias hit
→ SASIOVERLXRD
→ normal deterministic Spotify resolver
~~~

No fuzzy or AI call should be needed for the confirmed exact alias.

---

## 6. Candidate recovery is not execution authority

Non-negotiable rule:

~~~
candidate recovery
≠ automatic identity confirmation
≠ automatic memory confirmation
≠ automatic playback authority
~~~

A recovered candidate remains candidate evidence.

Only the existing trusted path may promote memory:

~~~
server-owned trusted candidate
→ explicit clarification selection
→ successful playback/action
→ MemoryLearner
→ confirmed alias
~~~

---

## 7. Proposed bounded recovery ladder

A future implementation may evaluate this order:

~~~
Tier 0
exact confirmed alias memory

Tier 1
existing deterministic Spotify resolution

Tier 2
bounded title-first / track-first Spotify retrieval

Tier 3
local lexical alias evidence
RapidFuzz / future indexed retrieval

Tier 4
optional future semantic evidence

→ bounded trusted clarification
~~~

Phase 1B should prefer deterministic Spotify evidence before adding heavier
semantic/vector retrieval.

---

## 8. Title-first / track-first recovery

A possible Phase 1B design:

1. Search using the most reliable known track-title span.
2. Fetch a bounded internal result pool.
3. Convert results to trusted SpotifyTrackRef objects.
4. Exclude unsupported Live/Concert/Tour versions.
5. Prefer normalized exact-title matches when available.
6. Apply existing deterministic evidence:
   - explicit artist / album / version;
   - saved;
   - Top Track;
   - Top Artist;
   - Recently Played;
   - deterministic relevance;
   - popularity only as final tie-break.
7. Exclude candidate IDs already presented in the current clarification
   sequence.
8. Return at most 3 public clarification candidates.

No client-provided URI/track ID may enter this path.

---

## 9. "None of these" behavior

A future clarification contract may support a reviewed phrase such as:

~~~
都不是
不是這些
換一批
none of these
~~~

This must **not** allow arbitrary client paging parameters or candidate IDs.

Recommended design:

~~~
clarification_token
→ server-owned clarification context
→ server-owned retrieval cursor/state
→ next bounded trusted candidates
~~~

The client only asks for another bounded page.

The server decides which trusted candidates belong to that page.

---

## 10. Boundedness

Candidate recovery must be bounded.

Accepted Phase 1B limits:

~~~
internal Spotify retrieval pool: <= 20
public clarification candidates: <= 3
successful user-visible continuation rounds: at most 2
initial title-first fetch: server-owned offset 0, not a continuation round
provider continuation offsets: 10, then 20
~~~

The initial title-first fetch creates the initial clarification page. A local
or provider page returned after an exact reviewed continuation consumes one
shared round, rotates the clarification token, and retires the old token as
USED. A third continuation is exhausted. Offsets and duplicate suppression
remain server-owned.

Do not permit:

- unbounded Spotify pagination;
- arbitrary search crawling;
- full-account Library enumeration;
- client-controlled offsets that can bypass server policy.

---

## 11. Duplicate / exhaustion behavior

The server should track candidates already shown for the active clarification
context.

If another page is requested:

~~~
new pool
→ remove already-shown trusted IDs
→ rank remaining candidates
→ return next <= 3
~~~

When no useful trusted candidates remain:

~~~
safe "not found / please specify artist or album"
~~~

Do not fall back to arbitrary AI-selected provider IDs.

---

## 12. Preference memory is separate from alias memory

The STAY example exposes another future distinction.

Current alias memory learns mappings such as:

~~~
Sad overlxrd
→ SASIOVERLXRD
~~~

But repeated selection of:

~~~
"Stay"
→ STAY — The Kid LAROI, Justin Bieber
~~~

is not necessarily an ASR alias.

It may represent **track preference / selection history**.

Do not overload artist alias memory with this meaning.

A future preference-memory design may use prior successful selections as a
ranking signal, but that requires a separate schema/authority review.

For v1.0/Phase 1B, it is acceptable to solve candidate recovery first without
adding persistent track-preference memory.

---

## 13. Memory-learning boundary

Candidate recovery itself must not write confirmed memory.

Allowed:

~~~
candidate recovered
→ user selects candidate
→ playback succeeds
→ existing MemoryLearner rules decide whether an alias confirmation event exists
~~~

Not allowed:

~~~
candidate appears in second search page
→ write confirmed memory
~~~

Not allowed:

~~~
RapidFuzz score high
→ write confirmed memory
~~~

Not allowed:

~~~
Local AI says candidate is correct
→ write confirmed memory
~~~

---

## 14. Tests required before implementation acceptance

At minimum:

### STAY pagination/recovery

~~~
initial 3 do not contain desired track
→ "none of these"
→ second bounded page contains desired trusted track
→ clarification still required
→ no automatic playback
~~~

### Duplicate suppression

~~~
page 2
→ does not repeat page 1 provider IDs
~~~

### Exhaustion

~~~
no trusted candidates remain
→ safe failure
→ no AI/provider-ID fabrication
~~~

### Live exclusion

~~~
recovery pool contains Live / Concert versions
→ unsupported candidates excluded
~~~

### Explicit metadata precedence

~~~
user provides artist/album/version
→ recovery never overrides those constraints
~~~

### Sad overlxrd first occurrence

~~~
no exact memory
→ trusted candidate recovery
→ clarification
→ explicit selection
→ successful playback
→ confirmed alias
~~~

### Sad overlxrd second occurrence

~~~
restart
→ exact confirmed alias hit
→ no fuzzy/AI needed
~~~

### Poisoning

~~~
unselected recovered candidate
→ never confirmed
~~~

### Playback failure

~~~
selected recovered candidate
→ playback fails
→ no confirmed memory
~~~

### Client authority

Reject any attempt by a client to submit:

- Spotify URI;
- Spotify track ID;
- arbitrary candidate index outside live server context;
- arbitrary paging cursor not issued by the server;
- memory trust state.

---

## 15. Relationship to search optimization

This Phase 1B problem is different from the future large-memory search
optimization documented in:

~~~
docs/semantic_recovery/SEARCH_OPTIMIZATION.md
~~~

Candidate recovery asks:

> How do we obtain the correct trusted candidate when the first Spotify
> candidate set is insufficient?

Search optimization asks:

> How do we make a large local alias-memory corpus fast?

Do not introduce FTS5, SymSpell, vectors, or HNSW merely to solve the STAY
candidate-page problem.

---

## 16. Scheduling recommendation

This work is deliberately deferred.

When resumed, use a dedicated branch from the then-latest main, for example:

~~~
feat/spotify-candidate-recovery-phase1b-<base-sha>
~~~

Do not mix it with:

- personalization acceptance;
- Local AI promotion;
- Semantic Memory database migrations;
- unrelated Spotify controls;
- release cleanup.

Suggested implementation scope:

~~~
one Phase 1B task
→ candidate retrieval/recovery
→ bounded "none of these" continuation
→ tests
→ focused Siri/Spotify acceptance
~~~

---

## 17. Product goal

The user experience should eventually become:

~~~
User:
"播放 Stay"

Agent:
offers 3 trusted candidates

User:
"都不是"

Agent:
offers another bounded trusted set

User:
selects STAY — The Kid LAROI, Justin Bieber

Agent:
plays it

Later:
memory/personalization may help rank that choice earlier,
but only through separately reviewed trust rules.
~~~

And for learned ASR aliases:

~~~
first time:
misrecognition
→ trusted recovery
→ clarification
→ successful playback
→ learn

next time:
exact confirmed memory hit
~~~

That is the intended Phase 1B direction.
