# Stage B final v1 pre-seal corpus

These 3,000 rows were selected from the frozen, independently accepted v6 pool
using a deterministic whole-source-group assignment. `held_out.jsonl` is an
assigned Stage B test split, but it is **not sealed**. No training, model compute,
calibration, benchmark promotion, Semantic Memory, or Local AI fallback is
authorized by these artifacts. The 600 excluded candidates remain in frozen v6.

`selection_manifest.json` binds input identities, output hashes, quotas, and
coverage. `corpus_manifest.json` is the authoritative protocol validator's
result. `provenance_manifest.json` records sanitized review provenance.
