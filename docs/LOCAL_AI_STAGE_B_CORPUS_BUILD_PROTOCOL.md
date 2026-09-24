# Local AI Stage B Corpus Build Protocol

**Status: frozen protocol, final-v1 split assigned before sealing.** This
protocol freezes the offline corpus-build rules and near-duplicate policy.
`artifacts/local_ai/stage_b/final_v1/` now contains a separately reviewable
3,000-row whole-group split. Held-out sealing, training, fine-tuning,
inference, model download, and production Local AI fallback remain unauthorized.

## 1. Frozen identities

The final-v1 build uses these identities:

```text
corpus_protocol_version: stage-b-corpus-build-v1
record_schema_version: 1
near_duplicate_policy_version: stage-b-near-duplicate-v1
```

The reviewed Stage A fixture remains permanently excluded from Stage B
generation and adaptation:

```text
path: tests/fixtures/ai_intent_cases.json
rows: 109
sha256: 60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55
```

It may be used only by the existing approved leakage/reference check and the
final untouched regression. It must not enter generation prompts, training,
validation, calibration, threshold fitting, paraphrase generation, or manual
correction.

A deterministic 3,000-row train/validation/held-out assignment now exists in
`artifacts/local_ai/stage_b/final_v1/`. Its held-out partition is assigned but
not sealed. The target counts and gates remain those in
[`LOCAL_AI_STAGE_B_ADAPTATION_PLAN.md`](LOCAL_AI_STAGE_B_ADAPTATION_PLAN.md).

## 2. Construction authority

The future build must keep these authorities separate and auditable:

```text
candidate utterance generation
    → label assignment
    → independent label review
    → group-aware final split assignment
    → validation and manifest generation
    → held-out sealing
```

The candidate being evaluated (`laya` or `decider`) may not generate or review
its own final held-out labels. Candidate generation is only a source of
proposed paraphrases; every accepted row needs independent review. The review
record must identify an opaque reviewer role/id, not a personal identity or
account credential.

`source_group_id` owns the split boundary. All paraphrases, ASR variants,
translations, punctuation variants, and the same underlying entity/template
group stay together. A split assignment is final only after leakage and
near-duplicate validation passes.

## 3. Near-duplicate policy

The implementation is in
[`scripts/local_ai_stage_b_corpus.py`](../scripts/local_ai_stage_b_corpus.py).
It uses only the Python standard library and has no network, subprocess, model,
Spotify, LM Studio, or Windows dependency.

### 3.1 Exact representation and final decision

For comparison only, normalize each utterance as follows:

1. Unicode NFKC;
2. Unicode casefold;
3. remove Unicode punctuation characters;
4. remove whitespace characters;
5. form a **set** of character 3-grams;
6. compute exact set-Jaccard similarity:
   `intersection / union`.

If normalized text is identical, the relation is `duplicate`. Otherwise,
similarity `>= 0.85` is `near_duplicate`; lower similarity is `distinct`.
The exact Jaccard result is the final rejection decision. Traditional/Simplified
conversion remains **not implemented** and is not silently introduced by this
policy.

For the 3,000-row target, pair comparisons are restricted to different splits
when invoked by corpus validation. The authoritative validator precomputes the
normalized text and character n-gram set once per record, then compares every
relevant cross-split pair with exact set-Jaccard. No approximate filter may
skip a pair before that exact decision.

The frozen configuration retains the following SimHash fields as
non-authoritative advisory metadata for diagnostics and future optimization
research only:

```text
candidate_filter: simhash64_hamming_v1
hash_function: BLAKE2b-64
hash_bits: 64
hash_seed: 0x53544231
candidate_hamming_threshold: 12
```

These SimHash values are not consulted to suppress an authoritative
comparison, and they cannot create a completeness guarantee. Exact Jaccard is
the only near-duplicate rejection authority. The advisory metadata,
normalization, n-gram size, similarity threshold, cross-split behavior, and
configuration hash are serialized in every validation manifest.

### 3.2 Frozen protocol configuration

`validate_protocol_corpus()` and `validate_corpus(...,
enforce_protocol_counts=True)` fail closed unless the complete active
near-duplicate configuration hash equals:

```text
64045462fe025b66dd5346df1e1d80cc886ab5e1fb1e8495fa57fe9aa9eb6ae7
```

The implementation stores this value as the literal
`FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256`; it is not derived from the
mutable default configuration. The default configuration is tested separately
to ensure it still matches this reviewed identity.

This protects every frozen field, including the algorithm, normalization,
n-gram size, threshold, cross-split mode, and retained SimHash advisory
metadata. An alternate configuration is not silently replaced. It may be used
only with compact research/unit validation where protocol counts are not
enforced.

### 3.3 Synthetic calibration fixture

Threshold selection is frozen from a small synthetic policy fixture only:

```text
path: tests/fixtures/stage_b_near_duplicate_policy_cases.json
canonical-json-sha256: eadd304a4b6abfab262f2d4395edcd67d6eda9522b3020337517a73720dd6e85
near-duplicate-config-sha256: 64045462fe025b66dd5346df1e1d80cc886ab5e1fb1e8495fa57fe9aa9eb6ae7
```

The fixture is explicitly synthetic, contains no Stage A rows, and is marked
forbidden as training data. It covers punctuation, whitespace, case, NFKC and
mixed-language variants, an ASR-like near duplicate, one-character distinct
titles, different tracks, different request families, Chinese partial overlap,
and boilerplate-prefix collisions.

The selected `0.85` threshold lies between the fixture's highest labeled
`distinct` similarity (`0.666667`) and its lowest non-identical labeled
`near_duplicate` similarity (`0.888889`). The fixture is not tuned after any
real Stage B row exists. Changing the frozen config changes its deterministic
config hash and requires a new independent review before corpus generation.

## 4. Separate provenance manifest

The closed `StageBRecord` schema is not expanded with reviewer/account fields.
`build_provenance_manifest()` emits a separate sanitized manifest containing at
least:

- corpus protocol version;
- generator version;
- generation source/category;
- opaque reviewer role/id;
- closed review status;
- deterministic review timestamp/record policy;
- split-assignment stage;
- validation tool version;
- canonical corpus SHA-256;
- final per-split SHA-256 values;
- near-duplicate configuration SHA-256;
- provenance manifest SHA-256.

It does not accept or emit real personal identity, account identifiers, raw
private logs, credentials, OAuth material, tokens, private paths, or raw model
output. Row-level source groups and template families remain in the reviewed
record schema; they are not an authority object.

## 5. Held-out sealing procedure

The future corpus build must execute this sequence and preserve its evidence:

1. generate candidate utterances from approved non-Stage-A sources;
2. assign provisional labels and source groups;
3. independently review labels and record sanitized review status;
4. run schema, security, Stage A leakage, exact duplicate, group, and
   near-duplicate validation;
5. perform group-aware train/validation/held-out split assignment;
6. generate canonical corpus and per-split hashes;
7. keep validation available for adaptation/calibration only;
8. seal the held-out Stage B test read-only, with labels unavailable to
   training, checkpoint, threshold, or calibration code;
9. freeze the protocol/provenance manifest and final split hashes;
10. request separate compute authorization only after the frozen evidence is
    independently reviewed.

No training or compute authorization is implied by a passing source test or a
valid synthetic fixture. The RX 9070 XT/backend qualification remains a
separate gate.

## 6. Required offline checks

The first build must retain focused tests for:

- deterministic policy results across runs and input order;
- punctuation, spacing, case, NFKC/fullwidth, and mixed-language normalization;
- obvious near duplicates and distinct entity/request combinations;
- same source group and near-duplicate cross-split rejection;
- explicit exclusion of Stage A from policy calibration;
- deterministic manifest and config hashes;
- sanitized provenance fields;
- absence of network, subprocess, model, and external-runtime dependencies.

The current tests are synthetic/offline evidence only. They do not authorize
live Windows, Spotify, Siri, LM Studio, model, deployment, or production
fallback behavior. `LOCAL_AI_FALLBACK_APPROVED=false` remains mandatory.
