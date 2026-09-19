# Semantic Memory Search Optimization

Status: **Research-backed roadmap / not yet approved for implementation**

This document records an open-source-informed search strategy for making Local Semantic Recovery fast as the alias database grows.

It does **not** change Phase 1 authority rules:

- only exact, confirmed, active, non-conflicted aliases may auto-canonicalize;
- fuzzy, FTS, spelling-correction, vector, and AI results are candidate/evidence only;
- search speed never grants execution authority;
- provider IDs used for playback remain server-owned trusted data.

The purpose of this roadmap is to make candidate retrieval faster **without weakening the trust model**.

---

## 1. Current baseline

Phase 1 already uses the right first optimization:

```text
SQLite persistent source of truth
        ↓ startup/rebuild
RAM dictionary of confirmed active non-conflicted aliases
        ↓
exact alias lookup
```

Exact confirmed aliases should continue to use the in-memory dictionary first.

For the common learned-alias path, disk search and AI should not be required.

Conceptually:

```text
normalized alias
→ RAM hash lookup
→ exact confirmed hit
→ canonical entity
→ existing deterministic resolver
```

This remains the fastest and safest path.

Current candidate-only fuzzy retrieval uses RapidFuzz after exact lookup misses.

---

# 2. Research summary

The following open-source technologies are useful reference points.

## 2.1 RapidFuzz

Project/documentation:

- https://github.com/rapidfuzz/RapidFuzz
- https://rapidfuzz.github.io/RapidFuzz/Usage/process.html

RapidFuzz exposes candidate-search APIs such as:

- `process.extract`
- `process.extractOne`
- `process.extract_iter`
- `process.cdist`

Useful controls include:

- scorer selection;
- top-k / `limit`;
- `score_cutoff`;
- `score_hint`;
- preprocessing hooks.

### Fit for this project

RapidFuzz is a strong Phase 1 / early Phase 2 choice because:

- the project already needs edit-like matching for ASR aliases;
- it can rank a bounded trusted alias vocabulary;
- it does not require a separate service;
- results can remain candidate-only;
- the implementation is easy to benchmark and fail closed.

### Limitation

A full scan still scales with the number of candidate strings.

For small and medium local alias sets this may be completely acceptable.

Do not add a more complicated index until Windows-host measurements show that the full scan is a meaningful latency or CPU problem.

---

## 2.2 SQLite FTS5

Official documentation:

- https://www.sqlite.org/fts5.html

FTS5 provides indexed full-text search inside SQLite.

Relevant features include:

- prefix indexes;
- Unicode tokenization;
- external/contentless index options;
- BM25-style ranking helpers;
- a built-in `trigram` tokenizer for substring matching.

The trigram tokenizer can support indexed substring-style matching instead of requiring a normal full-table text scan.

### Fit for this project

FTS5 is especially attractive because semantic memory already uses SQLite.

A future design can keep:

```text
aliases table = authoritative data
FTS5 table     = derived retrieval index
```

This avoids deploying another database or daemon.

Recommended use:

```text
query alias
→ FTS5 prefilter top-N alias rows
→ RapidFuzz rerank the small candidate set
→ candidate evidence only
```

FTS should **not** directly select a canonical entity.

### Important short-string limitation

SQLite's FTS5 trigram tokenizer is based on sequences of three characters.

Short queries can therefore behave differently from longer aliases, and full-text trigram matching cannot be treated as a replacement for legitimate one- or two-character entities.

The project already requires support for legitimate short entity names.

Therefore:

```text
short alias
→ exact RAM / deterministic path / bounded RapidFuzz
→ do not rely on trigram FTS as the only retrieval mechanism
```

### FTS index failure

The FTS table must be considered a derived optimization.

If it is:

- unavailable;
- corrupted;
- unsupported by the local SQLite build;
- stale;
- migration-incompatible;

the Agent must fall back to the existing deterministic exact/RapidFuzz path.

An FTS failure must never disable normal commands.

---

## 2.3 SymSpell

Reference project:

- https://github.com/wolfgarbe/SymSpell

SymSpell uses a precomputed symmetric-delete dictionary to reduce candidate-generation work for spelling correction.

Its design is interesting when:

- the alias dictionary becomes large;
- errors behave like bounded edit/spelling errors;
- low-latency lexical correction matters.

### Possible fit

A future experiment could compare:

```text
RapidFuzz full scan
vs
FTS5 prefilter + RapidFuzz
vs
SymSpell candidate generation + RapidFuzz
```

using the project's real Siri/ASR correction corpus.

### Why it is not the current default

The project's core error class is not ordinary dictionary spelling correction.

Stylized names such as:

```text
SASIOVERLXRD
←→
Sad overlxrd
```

come from speech recognition, pronunciation, branding, spacing, and transcription behavior.

Confirmed real Siri aliases are still more trustworthy than assuming a generic spelling-correction model will understand these transformations.

SymSpell should therefore remain a measured candidate-retrieval experiment, not an authority mechanism.

Before adopting it, review:

- operational complexity;
- memory cost of delete dictionaries;
- multilingual / Chinese behavior in the actual corpus;
- package/library license compatibility;
- maintenance status;
- measurable incremental value over RapidFuzz/FTS5.

---

## 2.4 Trie / radix structures

A compact trie can help with:

- prefix lookup;
- autocomplete;
- large static dictionaries;
- fast known-prefix narrowing.

One mature Python-oriented reference is:

- https://github.com/pytries/marisa-trie

### Fit for this project

A trie is potentially useful if future UX introduces:

- local alias autocomplete;
- management UI search;
- prefix-based entity lookup;
- very large mostly-static vocabularies.

It is less directly useful for noisy ASR edits than RapidFuzz or trigram retrieval.

It should not be added simply because it is fast.

Use it only if prefix-style access becomes a real measured requirement.

---

## 2.5 sqlite-vec

Reference project:

- https://github.com/asg017/sqlite-vec

`sqlite-vec` provides vector storage/search as a SQLite extension and is attractive for a local-first architecture because it keeps vector retrieval close to the existing SQLite database.

However, its upstream project currently describes itself as **pre-v1**, meaning breaking changes should be expected.

### Fit for this project

Potential future Phase 3 use:

```text
user-authored / Siri-transcribed utterance
→ local embedding
→ sqlite-vec nearest-neighbor candidates
→ deterministic candidate validation
→ clarification
```

It must not become:

```text
nearest vector
→ automatic confirmed alias
→ execution
```

### Adoption rule

Do not add vector memory until:

1. Phase 1 runtime acceptance is complete;
2. real alias corpus exists;
3. lexical retrieval misses are measured;
4. vector retrieval demonstrates incremental recall;
5. false candidate risk is measured;
6. privacy and local embedding cost are accepted;
7. dependency/version stability is reviewed.

---

## 2.6 hnswlib / HNSW

Reference:

- https://github.com/nmslib/hnswlib

HNSW is a common approximate-nearest-neighbor approach for high-dimensional vector search.

It is useful when vector collections become large enough that brute-force vector comparison is too slow.

### Fit for this project

HNSW is **not** a near-term alias-search requirement.

It becomes relevant only if:

- semantic/vector memory is actually adopted;
- vector counts become large;
- measured brute-force vector latency becomes unacceptable.

Adding ANN before those conditions would increase complexity without improving the common exact-alias path.

---

# 3. Recommended retrieval architecture

The recommended long-term retrieval stack is hierarchical.

```text
Input text
   ↓
EntityNormalizer
   ↓
┌─────────────────────────────────────┐
│ Tier 0 — exact confirmed RAM alias │
└─────────────────────────────────────┘
   │ hit
   └──→ canonical entity
   │ miss
   ▼
┌─────────────────────────────────────┐
│ Tier 1 — bounded lexical retrieval │
│ RapidFuzz                           │
└─────────────────────────────────────┘
   │
   ▼
candidate evidence
   │
   │ when measured scale requires it
   ▼
┌─────────────────────────────────────┐
│ Tier 2 — indexed lexical prefilter │
│ SQLite FTS5 trigram/prefix         │
└─────────────────────────────────────┘
   ↓ top-N
RapidFuzz rerank
   ↓
candidate evidence
   │
   │ optional future experiment
   ▼
┌─────────────────────────────────────┐
│ Tier 3 — specialized typo index    │
│ SymSpell / trie where justified    │
└─────────────────────────────────────┘
   ↓
candidate evidence
   │
   │ future only
   ▼
┌─────────────────────────────────────┐
│ Tier 4 — semantic/vector retrieval │
│ sqlite-vec / HNSW                  │
└─────────────────────────────────────┘
   ↓
candidate evidence
   │
   ▼
existing deterministic clarification
   ↓
explicit user selection
   ↓
successful action
   ↓
MemoryLearner may confirm
```

Important:

Tier number is not trust level.

A result from a more sophisticated tier does not gain more execution authority.

---

# 4. Fast path

The exact confirmed-alias path should remain independent from future search complexity.

Recommended data shape:

```text
(normalized_alias, scope)
→ entity reference
```

A simple in-process mapping should remain the normal path for learned confirmed aliases.

Requirements:

- built at startup/rebuild from SQLite;
- confirmed only;
- active only;
- conflicted aliases excluded;
- deterministic normalization before key lookup;
- atomic swap/rebuild behavior where practical;
- no network access;
- no Local AI call;
- no fuzzy scan.

Performance target remains the existing design target:

```text
exact confirmed alias lookup P95 < 5 ms
```

This target must be measured on the real Windows host before being called accepted.

---

# 5. Candidate search: prefer prefilter + rerank

For large alias sets, avoid using a new retrieval engine as the final ranking authority.

Prefer:

```text
cheap index
→ retrieve N plausible rows
→ existing normalization
→ RapidFuzz deterministic rerank
→ top-k evidence
```

Advantages:

- the index does not define identity;
- RapidFuzz behavior stays visible and testable;
- candidate set remains bounded;
- failures can fall back safely;
- different index backends can be benchmarked without changing execution authority.

Suggested initial bounds for experimentation, not production guarantees:

```text
prefilter N: 20–100
final fuzzy top-k: 3–10
```

Actual values require corpus/latency testing.

Do not expose these weights/bounds as remote client authority.

---

# 6. SQLite FTS5 design sketch

Do not implement this until benchmark evidence justifies Phase 2.

A possible derived index:

```sql
CREATE VIRTUAL TABLE alias_fts USING fts5(
    normalized_alias,
    compact_alias,
    content='aliases',
    content_rowid='alias_pk',
    tokenize='trigram'
);
```

This is only a design sketch.

Migration design must account for:

- SQLite build feature detection;
- initial backfill;
- insert/update/delete synchronization;
- recovery/rebuild;
- corruption;
- index versioning;
- short aliases;
- schema rollback strategy.

Alternative contentless/external-content modes should be benchmarked instead of chosen by assumption.

### Rebuild rule

The authoritative `aliases` table wins.

If the FTS index disagrees:

```text
aliases table
→ rebuild derived FTS index
```

Never promote an FTS-only row to trusted memory.

---

# 7. Search scopes

Future search indexes should be scoped by entity domain.

For example:

```text
spotify_artist
spotify_track
app
audio_device
future_document_entity
```

Do not fuzzy-search every semantic-memory row globally if the active command already constrains the entity type.

Use available deterministic context to reduce work:

```text
spotify artist request
→ search only artist aliases

app request
→ search only app aliases
```

This improves both speed and safety.

The existing reserved `scope_context` field must not silently gain execution semantics without a reviewed design.

---

# 8. Cache strategy

Recommended order:

## Level A — confirmed RAM exact cache

Always on when semantic memory is enabled.

Source of truth remains SQLite.

## Level B — optional normalized candidate cache

Only consider after profiling.

Possible cache key:

```text
(entity_type, normalized_query, memory_generation)
```

Do not cache forever.

Invalidate on:

- confirmed alias write;
- conflict;
- disable/remove;
- DB rebuild;
- schema/index generation change.

## Level C — expensive semantic cache

Only relevant for future embeddings/AI.

Must be bounded and privacy-reviewed.

Do not persist arbitrary raw Siri text merely to improve cache hit rate.

---

# 9. Benchmark before adopting a new search backend

Use the existing performance sizes:

```text
100 aliases
1,000 aliases
10,000 aliases
50,000 aliases
```

Add comparison rows for:

```text
RAM exact lookup

RapidFuzz full scan

FTS5 prefilter
FTS5 prefilter + RapidFuzz rerank

SymSpell candidate retrieval (experimental)

future vector brute force
future ANN/HNSW
```

For each candidate backend measure:

- startup/index build;
- warm lookup P50/P95/P99;
- cold lookup P50/P95 where meaningful;
- memory/RAM;
- SQLite/index size;
- write/update cost;
- rebuild cost;
- top-k recall against a labeled fixture;
- wrong-candidate rate;
- conflict behavior;
- failure fallback.

Search latency alone is not enough.

A faster backend that loses the correct candidate or raises poisoning risk is a regression.

---

# 10. Corpus design

Performance and quality tests should use a stable corpus.

Include:

- confirmed real Siri aliases;
- stylized Latin artist names;
- Traditional/Simplified variants;
- case/space/punctuation variants;
- one-character and two-character legitimate names;
- same-name artists;
- near-spelling but different artists;
- random unrelated aliases;
- long aliases;
- Unicode edge cases;
- wrong fuzzy leader examples;
- conflict rows;
- poisoning attempts.

For larger benchmark sizes, use synthetic filler aliases **plus** the fixed labeled hard cases.

Do not let synthetic scale tests replace real ASR quality tests.

---

# 11. Decision rules by scale

These are recommended engineering rules, not accepted production thresholds.

## Small memory

If measured RapidFuzz full scan remains comfortably below the existing local-recovery latency budget:

```text
RAM exact
+ RapidFuzz
```

Keep it simple.

## Medium memory

If full-scan fuzzy latency becomes meaningful:

```text
RAM exact
+ SQLite FTS5 prefilter
+ RapidFuzz rerank
```

is the preferred next experiment.

## Large lexical dictionary

If FTS5 + RapidFuzz does not meet the measured requirement, compare:

- SymSpell;
- trie/radix structures where prefix behavior is useful;
- sharded/scoped indexes.

Do not immediately jump to vectors.

## Semantic memory

Only when lexical retrieval demonstrably cannot cover important real queries should vector retrieval be evaluated.

---

# 12. Why not make vector search the default?

Vector search is attractive, but the majority of confirmed alias memory should be exact.

For example:

```text
Sad overlxrd
→ confirmed SASIOVERLXRD
```

Once learned, the second request should be an exact dictionary lookup.

Calling an embedding model and ANN index for that request would be:

- slower;
- harder to debug;
- less deterministic;
- more memory intensive;
- unnecessary.

Vector retrieval should solve a demonstrated semantic-recall problem, not replace exact memory.

---

# 13. Why not let a high fuzzy score auto-confirm?

Because similarity is not identity.

Examples can have high lexical similarity but refer to different real entities.

Therefore no threshold such as:

```text
RapidFuzz >= 95
FTS rank top-1
SymSpell edit distance <= 1
vector cosine >= 0.95
```

may by itself produce:

```text
confirmed
```

or a trusted provider selection.

The trust transition remains:

```text
candidate evidence
→ deterministic clarification
→ server-owned selected entity
→ successful playback/action
→ MemoryLearner
→ confirmed
```

---

# 14. Failure hierarchy

Optional retrieval acceleration must fail downward.

```text
FTS unavailable
→ RapidFuzz full scan

RapidFuzz path fails
→ existing deterministic resolver/clarification

vector backend unavailable
→ lexical retrieval

all semantic-memory retrieval unavailable
→ pre-memory deterministic Agent behavior
```

Never fail upward into broader authority.

For example:

```text
FTS error
≠ call AI and trust answer

vector service error
≠ pick first Spotify candidate

index corruption
≠ mark alias confirmed
```

---

# 15. Dependency policy

Before adding any new retrieval dependency:

1. confirm a measured problem exists;
2. benchmark an implementation or prototype;
3. check maintenance status;
4. check Windows/Python support;
5. review license compatibility;
6. verify bounded memory use;
7. add failure-path tests;
8. keep it optional when practical;
9. keep SQLite authoritative;
10. document removal/fallback strategy.

Prefer built-in SQLite capabilities before introducing another daemon/database.

---

# 16. Recommended roadmap

## Phase 1 — current

```text
RAM exact confirmed alias
+ RapidFuzz candidate-only
+ SQLite persistent source of truth
```

No change to authority.

## Phase 1 acceptance

Finish real Windows / Spotify / Siri acceptance before optimizing prematurely.

## Phase 2A — benchmark lexical scale

Benchmark:

```text
RapidFuzz full scan
100 / 1k / 10k / 50k
```

If it is fast enough, stop.

No extra index is a valid result.

## Phase 2B — FTS5 prefilter experiment

Only if measurements justify it:

```text
FTS5 trigram/prefix candidate prefilter
→ bounded top-N
→ RapidFuzz rerank
```

Keep short-name fallback.

## Phase 2C — specialized lexical experiments

Only if still needed:

- SymSpell;
- trie/radix structures;
- scope-specific indexes.

Choose by measured corpus quality, not theoretical benchmark claims.

## Phase 3 — vector shadow research

If real user corpus shows lexical retrieval misses semantic equivalents:

```text
local embedding
→ sqlite-vec or another reviewed backend
→ shadow candidate comparison
```

No automatic rewrite.

## Phase 4 — vector candidate retrieval

Only after zero-authority shadow evaluation:

```text
vector
→ candidate set
→ deterministic clarification
```

Still no direct playback/trust promotion.

## Phase 5 — large-scale ANN

Only if vector counts and measured latency justify ANN/HNSW.

---

# 17. Near-term recommendation for this repository

Do **not** implement FTS5, SymSpell, sqlite-vec, or HNSW immediately.

The recommended next work remains:

1. complete Phase 1 runtime acceptance;
2. measure actual Windows latency at 100 / 1k / 10k / 50k aliases;
3. preserve the current RAM exact fast path;
4. keep RapidFuzz candidate-only;
5. add FTS5 only when measured full-scan cost justifies it.

The likely first search optimization after Phase 1 acceptance is:

```text
RAM exact confirmed aliases
        ↓ miss
entity-type scoped FTS5 trigram prefilter
        ↓ top-N
RapidFuzz rerank
        ↓
bounded candidate evidence
        ↓
existing clarification
```

This preserves the project's most important principle:

**make retrieval faster without making retrieval more authoritative.**
