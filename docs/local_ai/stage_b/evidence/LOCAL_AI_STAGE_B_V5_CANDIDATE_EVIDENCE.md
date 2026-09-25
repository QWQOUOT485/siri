# Stage B v5 Candidate Freeze — Issue #53

This is an offline, unsplit candidate/review pool, pending independent semantic
review. It does not select the final 3,000 rows, assign a split, seal held-out
data, run a model, or approve production fallback. The v4 artifacts remain in
`artifacts/local_ai/stage_b/` as historical audit evidence. The v4 generator
source remains retrievable from Git at
`68a71ed420467f1eebdf686f9268905af37e8146:scripts/local_ai_stage_b_candidate_corpus.py`.
V4 Packet 01 decisions were not imported.

## Generator and script boundary

`stage-b-candidate-generator-v5` fixes the five issue classes:

1. zh-Hans generation maps `著` to `着`. Separately,
   `scripts/data/stage_b_zh_hans_script_inventory_v1.json` pins a closed,
   reviewed set of allowed Han characters. The builder and review-source loader
   verify its canonical SHA-256 against a literal code constant. Every zh-Hans
   Han character outside that inventory fails closed. The inventory was curated
   from the corpus's Chinese vocabulary, with `著` excluded and required
   simplified characters added. It is a separate versioned file, not computed
   from the generation conversion table. This is a corpus-specific validation
   boundary, not a general Chinese script classifier. `沿著之前` and unmapped
   `龍` are both rejected by focused tests.
2. `play_en_punctuation_loss` uses ordinary spoken `by` and `from` carriers;
   the validator checks the non-entity carrier for generated slot delimiters.
3. Chinese volume controls place artist playback in a subordinate time clause;
   the control request is solely to set Spotify volume. A post-percent second
   playback imperative is rejected.
4. Chinese `unknown_missing_track` variants explicitly request an album.
   Bare `我要聽<entity>` / `我要听<entity>` surfaces are rejected.
5. The mixed shell-safety variant uses `幫我 run cmd /c ...` and remains
   `safety_only`, blocked by the production eligibility gate.

The inventory's canonical identity (excluding its `inventory_sha256` field) is
`0aa72c72acb984135507b72ea179cd3812c163d644ee1c03942a858aef8c0b36`.
The frozen Stage A fixture identity remains
`60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`;
the near-duplicate configuration remains
`64045462fe025b66dd5346df1e1d80cc886ab5e1fb1e8495fa57fe9aa9eb6ae7`.

## Corpus checks

| Check | v5 result |
| --- | ---: |
| Candidate rows / source groups / template families | 3,600 / 600 / 32 |
| Supported play / supported unknown | 1,800 / 1,260 |
| Deterministic only / safety only | 300 / 240 |
| zh-Hant / zh-Hans / mixed / en | 1,380 / 288 / 1,140 / 792 |
| Artist present / absent | 1,080 / 720 |
| Album present / absent | 1,080 / 720 |
| Both optional slots / neither | 720 / 360 |
| Stage A leakage | 0 |
| Exact duplicates | 0 |
| Same-group near duplicates | 0 |
| Cross-group near duplicates | 0 |
| Cross-group exact duplicates | 0 |
| Production scope mismatches | 0 |
| zh-Hans unreviewed script characters / `著` rows | 0 / 0 |
| English generated slot delimiters | 0 |
| Chinese compound volume/playback imperatives | 0 |
| Chinese bare `unknown_missing_track` | 0 |
| `執行 run cmd` surfaces | 0 |

The production gate admitted all 1,800 supported play and 1,260 supported
unknown rows, and blocked all 300 deterministic-only and 240 safety-only rows.
The English and mixed catalog retains 1, 2, 3, and 4+ word entity buckets;
both include digits, apostrophes, hyphens, periods, parentheses, and other
punctuation. The manifest records detailed per-slot morphology counts.

| Catalog language / slot | 1 word | 2 words | 3 words | 4+ words |
| --- | ---: | ---: | ---: | ---: |
| en artist | 27 | 40 | 39 | 26 |
| en track | 32 | 38 | 45 | 17 |
| en album | 34 | 32 | 43 | 23 |
| mixed artist | 38 | 57 | 57 | 38 |
| mixed track | 47 | 55 | 64 | 24 |
| mixed album | 48 | 48 | 60 | 34 |

For en entities, the catalog has 49 digit-bearing, 80 punctuation-bearing,
18 apostrophe-bearing, 43 hyphen-bearing, 17 period-bearing, and 10
parenthesis-bearing entries. The corresponding mixed counts are 70, 116,
25, 62, 25, and 16. Each count means at least one of artist, track, or album
in that catalog entry has the feature.

The review allocation is 12 packets of 300 rows, each candidate exactly once.
Packets are review allocations, not final splits. The initial review state is
`decision_count=0`, `reviewed=0`, `accepted=0`, `rejected=0`,
`needs_correction=0`, `conflict=0`, `pending=3600`.

## File SHA-256

These hashes are SHA-256 of the committed file bytes (LF line endings). The JSON manifests also contain
canonical content identities and self-hashes, checked by the review loader.

| v5 artifact | File SHA-256 |
| --- | --- |
| `candidate_corpus.jsonl` | `f648b916e14b56b94575534a318857fc2c208b75f656bead6561a37cf7b23cbe` |
| `entity_catalog.json` | `2b91ba5f2683813c0839530c0778351250e3b0854f12bc853ebe60e78e7123a7` |
| `generator_config.json` | `bbb87f3a8ea457b6f817733495eab9c907f78db180df26b7ac25c4a022677a8b` |
| `candidate_manifest.json` | `88dd004e5c1f53a3420e503b9c158037af07c6ab24dfe221ee87ac653cefb573` |
| `candidate_review_queue.jsonl` | `9ac6496934b014c3c021470e308cc28195eb358df9f91c9778c96d30166e4bb0` |
| `review/review_manifest.json` | `3b2785fe5043c8b3561d1bd8c17cd63677c376b3ba3671fa6a86440f611ad3ec` |
| `review/decisions/README.md` | `aed9c4637065889b25e689acb5863bf57176d0d950ea6d496072dcb1c70b8eea` |
| `scripts/data/stage_b_zh_hans_script_inventory_v1.json` | `1e350a7fc1d27b62e4fe265b7c817db1cec12710c53bf28961adb6fc4306d79a` |
| `review/packets/packet-01.jsonl` | `f35b6b0370691f687791709ea1db9a7cca2391fc2eb4d7e16cd2184fc38f2fd1` |
| `review/packets/packet-02.jsonl` | `bcd2af567c6a1f85abef280b7dc7bb8aa7067658b98dcc3196218f85133db438` |
| `review/packets/packet-03.jsonl` | `c3ff1fe3e814804b1b410bfde787186e002a35039148d06905a228ca662e446f` |
| `review/packets/packet-04.jsonl` | `e43b842f7958440297f8fdbb4bf482620cfef9c9dfbab08bf9ad0ebe13c904c7` |
| `review/packets/packet-05.jsonl` | `07bffd384e9a02e302f9ce3011f143d67c357ba660e816107f783c49eb6ebe39` |
| `review/packets/packet-06.jsonl` | `6bec70cfa496eb1180eb0ef9b75d4e843d1a426a86f0f8e09fcf80286f2d6ab8` |
| `review/packets/packet-07.jsonl` | `751dc1d0b503e35aa415b19e18f618d609e58bf2bed7697bf308a3181fbac2ee` |
| `review/packets/packet-08.jsonl` | `372546cef0b0bf9d70e2100b195eb0fccc848a97af36ed9887cb18dab4212c24` |
| `review/packets/packet-09.jsonl` | `a0b93e91bd352932e4b225b4a2dc9a159b93dfd44c8a0d4edd2a6db11aafce76` |
| `review/packets/packet-10.jsonl` | `e0abad7759cc1afa558599e7c4e1bafd3f57cedfee1ddf80efa41c34ee3af861` |
| `review/packets/packet-11.jsonl` | `a410c501e00b5c7bf3141ce1a7568fdcc8fc36cfbd6ffe8e0cf2f99f2b5c66d0` |
| `review/packets/packet-12.jsonl` | `81ff1e96f42c38f1947d6409ad76cb0efcc28eaed69e1262ac9df02e70633ef1` |

The candidate manifest's canonical source identity is
`ff1e4a89524be878c9aaa491cb978c753728ef45baed1051512ec0954e838950`;
the review manifest's canonical self-hash is
`08b1656fa6d4b12ba17ac4bedbb01dfa3e45ece413c72423009564ee55b84f9d`.

Independent semantic review remains the next gate. Neither the zero-defect
checks nor these frozen hashes count as reviewer acceptance.
