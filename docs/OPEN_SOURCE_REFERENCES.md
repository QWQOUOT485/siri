# Open Source References and Attribution Notes

Status: **Engineering reference / dependency provenance guide**

This document records open-source projects that this repository currently uses,
studies, or may evaluate later.

Its goals are:

1. make future implementation work easy to trace back to original projects;
2. record authors / maintainers and official repositories;
3. record the current license at the time of review;
4. distinguish **actual dependency** from **research/reference only**;
5. remind future contributors to re-check the exact version/license before
   shipping copied or bundled third-party code.

This is an engineering provenance document, not legal advice.

Before adding or distributing any new third-party dependency, verify the license
of the exact version/tag actually used.

---

## 1. RapidFuzz

**Current project relationship:** **USED dependency**

Current repository requirement:

```text
rapidfuzz>=3.9,<4.0
```

### Project

- Project: RapidFuzz
- Primary credited author / maintainer: **Max Bachmann**
- Additional copyright credit in upstream license: **Adam Cohen**
- Official repository:
  https://github.com/rapidfuzz/RapidFuzz
- Documentation:
  https://rapidfuzz.github.io/RapidFuzz/
- Process/search API:
  https://rapidfuzz.github.io/RapidFuzz/Usage/process.html

### License

**MIT License**

Upstream license currently credits:

- Copyright © 2020-present Max Bachmann
- Copyright © 2011 Adam Cohen

License page:

https://rapidfuzz.github.io/RapidFuzz/License.html

### Why this project references/uses it

Local Semantic Recovery uses RapidFuzz for bounded fuzzy candidate retrieval.

It is not identity authority.

Project rule:

```text
RapidFuzz result
→ candidate evidence
→ clarification when required
→ never automatic trust promotion by score alone
```

### Future implementation note

If RapidFuzz code is copied or vendored instead of consumed as a package,
preserve the required MIT copyright/license notice.

---

## 2. SQLite / FTS5

**Current project relationship:** **USED platform/database technology**  
**FTS5 search optimization:** **REFERENCE / future experiment**

### Project

- Project: SQLite
- Project architect / original developer: **D. Richard Hipp**
- Maintained by the SQLite development team
- Official website:
  https://www.sqlite.org/
- FTS5 documentation:
  https://www.sqlite.org/fts5.html
- Public-domain statement:
  https://www.sqlite.org/copyright.html

### License / copyright status

SQLite's core code and documentation are dedicated to the **Public Domain**.

The official SQLite copyright page states that SQLite code may be copied,
modified, published, used, compiled, sold, or distributed for commercial or
non-commercial purposes.

Important:

Some build-system scripts or separately sold proprietary SQLite extensions may
have different terms. Do not assume every product associated with SQLite is
public domain.

### Why this project uses/references it

Current semantic memory uses SQLite as the persistent source of truth.

Future search optimization may evaluate:

```text
SQLite FTS5 trigram/prefix prefilter
→ bounded candidate set
→ RapidFuzz rerank
```

FTS5 would be a derived search index only.

It must not become trust authority.

---

## 3. SymSpell

**Current project relationship:** **RESEARCH / REFERENCE ONLY**  
**Not currently a project dependency**

### Project

- Project: SymSpell
- Author / maintainer: **Wolf Garbe**
- Official repository:
  https://github.com/wolfgarbe/SymSpell

### License

Current upstream repository: **MIT License**

The current upstream README/license credits Wolf Garbe.

Important historical note:

Older SymSpell versions used LGPL licensing. If a future implementation copies,
vendors, forks, or pins an older release, verify the exact release license
instead of assuming current MIT terms apply retroactively.

### Why this project references it

SymSpell's symmetric-delete approach is useful research for fast spelling/error
candidate generation on large dictionaries.

Possible future benchmark:

```text
RapidFuzz full scan
vs
FTS5 prefilter + RapidFuzz
vs
SymSpell candidate generation + RapidFuzz
```

It is especially a candidate-generation reference, not trust authority.

For this project, noisy Siri/ASR transcription is not identical to ordinary
spelling correction, so real confirmed Siri aliases remain more trustworthy
than generic spelling-correction assumptions.

---

## 4. marisa-trie / Python marisa-trie

**Current project relationship:** **RESEARCH / REFERENCE ONLY**  
**Not currently a project dependency**

There are two relevant layers.

### Python wrapper

- Project: pytries/marisa-trie
- Credited package author: **Mikhail Korobov**
- Repository:
  https://github.com/pytries/marisa-trie
- Wrapper license: **MIT**

The Python package metadata currently describes the combined licensing as:

```text
MIT AND (BSD-2-Clause OR LGPL-2.1-or-later)
```

because it includes/bundles the underlying C++ MARISA library.

### Underlying C++ MARISA library

- Project: marisa-trie / libmarisa
- Copyright holder / author credit: **Susumu Yata**
- Repository:
  https://github.com/s-yata/marisa-trie
- License:
  **BSD-2-Clause OR LGPL-2.1-or-later**

### Why this project references it

Potential future use cases:

- compact static dictionaries;
- prefix search;
- autocomplete;
- large mostly-static alias vocabularies.

It is not the preferred solution for noisy edit-distance ASR recovery.

Before adopting the Python package, review both the wrapper and bundled C++
library license obligations for the exact version/distribution method.

---

## 5. sqlite-vec

**Current project relationship:** **FUTURE RESEARCH / REFERENCE ONLY**  
**Not currently a project dependency**

### Project

- Project: sqlite-vec
- Author / copyright credit: **Alex Garcia**
- Repository:
  https://github.com/asg017/sqlite-vec

### License

Upstream currently provides:

- **MIT License**
- **Apache License 2.0**

The upstream license files credit Alex Garcia.

### Stability note

The upstream project currently describes itself as **pre-v1**.

Therefore a future adoption review must consider:

- breaking API/schema changes;
- Windows/Python packaging;
- migration stability;
- extension loading behavior;
- exact release/version support.

### Why this project references it

Potential future local semantic/vector candidate retrieval:

```text
local utterance embedding
→ sqlite-vec nearest candidates
→ deterministic validation / clarification
```

Never:

```text
nearest vector
→ confirmed alias
→ direct execution
```

Vector retrieval remains deferred until a real user corpus demonstrates
incremental value beyond lexical retrieval.

---

## 6. hnswlib

**Current project relationship:** **FUTURE RESEARCH / REFERENCE ONLY**  
**Not currently a project dependency**

### Project

- Project: hnswlib
- Organization: **NMSLIB**
- Standalone HNSW implementation is credited by NMSLIB to **Yury Malkov**
- Repository:
  https://github.com/nmslib/hnswlib

Related HNSW publication authors include Yury A. Malkov and D. A. Yashunin.

### License

**Apache License 2.0**

### Why this project references it

hnswlib is a possible future approximate-nearest-neighbor backend if:

- vector memory is actually adopted;
- vector collections become large;
- brute-force vector retrieval becomes measurably too slow.

It is not needed for current alias memory.

Do not add ANN/HNSW complexity before profiling demonstrates a real requirement.

---

# 7. Current status summary

| Project | Author / maintainer credit | License | Current status in this repo |
|---|---|---|---|
| RapidFuzz | Max Bachmann; Adam Cohen credited in license | MIT | **Used dependency** |
| SQLite / FTS5 | D. Richard Hipp / SQLite team | Public Domain | SQLite used; FTS5 future optimization |
| SymSpell | Wolf Garbe | MIT (current upstream) | Reference only |
| pytries/marisa-trie | Mikhail Korobov | MIT wrapper | Reference only |
| libmarisa | Susumu Yata | BSD-2-Clause OR LGPL-2.1-or-later | Reference only |
| sqlite-vec | Alex Garcia | MIT / Apache-2.0 | Future reference only |
| hnswlib | NMSLIB; HNSW implementation credited to Yury Malkov | Apache-2.0 | Future reference only |

---

# 8. Rules for future coding agents

Before adding code based on an open-source project:

1. Open this file.
2. Open the upstream repository.
3. Verify the exact version/tag that will be used.
4. Re-check the license at that exact version.
5. Decide whether the work is:
   - idea/reference only;
   - package dependency;
   - vendored source;
   - modified/forked source.
6. Record the exact version in this document before release/distribution.
7. Preserve required copyright/license notices.
8. If Apache-2.0 code is distributed, review NOTICE/attribution requirements.
9. If LGPL code is selected, review linking/distribution obligations before
   adoption.
10. Do not copy source snippets from an upstream project into this repository
    without recording where they came from and confirming the license permits
    the intended use.
11. Prefer using a normal package/dependency over copying upstream source when
    practical.
12. Do not claim that an algorithm idea implies permission to copy a particular
    implementation.
13. If license terms are unclear, stop and perform a dedicated license review
    before implementation.

---

# 9. Third-party notices before public/commercial distribution

Before a public binary/package/commercial release, create or update a formal:

```text
THIRD_PARTY_NOTICES.md
```

or equivalent distribution notice containing the third-party components that
are actually shipped.

That shipping notice should be generated from **actual pinned dependencies**,
not every research project listed in this file.

Research/reference-only entries do not become shipped dependencies merely
because they are documented here.

---

# 10. Relationship to semantic-memory roadmap

For the current Local Semantic Recovery search strategy, read:

- `docs/semantic_recovery/SEARCH_OPTIMIZATION.md`
- `docs/semantic_recovery/REFERENCES.md`
- `docs/semantic_recovery/IMPLEMENTATION_PLAN.md`

Current preferred progression remains:

```text
RAM exact confirmed alias
→ RapidFuzz candidate retrieval
→ measured FTS5 prefilter experiment if needed
→ specialized lexical experiments only if justified
→ vector/ANN only much later
```

Search technology may improve retrieval performance.

It never changes the project's trust rule:

**retrieval evidence is not execution authority.**
