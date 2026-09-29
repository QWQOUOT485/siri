# Stage B Laya span, typed, and validity diagnosis v3 — 2026-09-29

**Current result:** `LAYA_SPAN_TYPED_VALIDITY_DIAGNOSIS_V3_COMPLETED`. This is a single validation-only diagnostic, not model quality acceptance or authorization to train. The complete sanitized record, including every case ID, matrix, distribution, identity, and counter, is [the canonical JSON](LAYA_SPAN_TYPED_VALIDITY_DIAGNOSIS_V3_2026-09-29.json) (canonical SHA-256 `43d8b82429a77ac03b95cb461715ea03321c551c16a6aabac5ca25d1be020c9d`).

## Provenance and correction

- Exact starting `origin/main`: `b779b3361f5bcf22c505d0db69c126af8240d30a` (PR #91 merged). PR #91's corrected canonical result is `70a1f83e18c9df42d5a7163f16c108beb01c485fdab60882310f6f95288ab310`; its frozen runner SHA/blob are `20db77c91261aea73b61f3a6c70aad1cc25d65eeca1affbdd025f121e32ded9e` / `ce5b958e50a12740b2d9ec69ca2ce5e88c7725d1`, and test blob is `166e9a776a364f347827a47b82c57b84e5bf1bd5`.
- PR #91's one live v2 run reached `diagnose()` but the sanitizer called `.lower()` on integer BIO keys. Its diagnosis was not durably emitted; v2 remains a historical blocker. V3 copies the reviewed runner, accepts exact `int` dictionary keys, checks sensitive substrings only on exact `str` keys, and recursively checks all values. Bool, float, `None`, tuple, `Path`, and object keys fail closed. Historical v2 source/tests remain unchanged.
- V3 runner/test were frozen before compute in `aaf0aec16eee7948e20da3b93012ea74ee6c0070`; runner byte SHA-256 `d64776c85a263dddb9131c63c79e2a0cd5e46a9ced5f61e87508d5479f2fa87a`. No runner/test changes followed the live invocation.
- PR #88 canonical identity `babb424a086de8bbf83ff5ab68a91dcea39cb5ae1e1247dc5347a1cd40f6a42b`; PR #90 canonical identity `607c731fce78468b4427d1f16238d8515dfa740a6a5f4450fbf57408cfd6b156`.

## One live boundary

The qualified Python ran with `-B -X utf8`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `GIT_OPTIONAL_LOCKS=0`. Unique selected device: `cuda:1`, AMD Radeon RX 9070 XT / `gfx1201`; the iGPU was `cuda:0`. Strict load and full model residency on `cuda:1` passed, `cpu_fallback=false`. The external read-only checkpoint was `<external-adaptation-root>/6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a/final.pt`, SHA-256 `199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d`, 177,394,599 bytes.

Transport was `explicit-v3`: child return 0, exactly one stdout marker, `TRANSPORT_OK`, null structured transport error, child stderr retained, and no primary-result `atexit`. The child produced one base load, one checkpoint deserialize/restore, one validation pass, 34 forward batches, 540 shared decisions, and 540 calls to each decoder. Additional model forwards for the second decoder: 0. Training steps, backward calls, optimizers, and schedulers: 0. The 600 frozen validation rows comprised 100 groups, 540 supported inputs, and 60 blocked before rendering; validation byte SHA-256 `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a`. Train, held-out, and Stage A were not opened as row sources. The diagnostic scratch directory was absent before dispatch and verified absent after parent cleanup.

Before and after identities are equal: Laya source `42626c348753fbb17572a813127df2278a1ec527` clean, canonical model aggregate `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf`, primary weight `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204`, qualified venv inventory `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337`, checkpoint, validation, and accepted evidence. Post-validation parameter hashes: encoder `e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812`, act head `7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d`, typed `a5c3f736e7c943ab39039eb240cf635df22521d74fe159a01f899d149816660b`, span `864e146331b596e2d555ecc34cd4e968a0f3ee233721f5ebd3e18f72c23afd20`, validity `9e339959e40062df3fda976970361f7fc53793ee5b616b6b01eea06b35bdb2aa`.

VRAM allocated/reserved bytes: baseline 0/0; after base load 1,307,833,856/1,333,788,672; after restore 1,307,859,456/1,333,788,672; final 1,341,413,888/1,371,537,408; peak allocated 1,360,115,712. Base load 13.968 s, checkpoint restore 1.006 s, validation 6.273 s.

## Reproduction and diagnosis

PR #88 reproduction passed **540/540** for case ID, typed index, validity gate, historical prediction object, and S3 prediction object. Typed and validity probabilities also matched exactly (maximum absolute delta 0). The prior 218 failed play case-ID set and the 70 typed-not-play case-ID set match exactly. The complete 70 IDs and 218 category assignments are in the JSON.

BIO label IDs: `0 O`, `1 B-TRACK`, `2 I-TRACK`, `3 B-ARTIST`, `4 I-ARTIST`, `5 B-ALBUM`, `6 I-ALBUM`. Rows are gold, columns predicted. Across the 300 gold plays, the 7×7 all-language confusion matrix is:

```text
1920   2  32   0   8  0  46
 205  17  59   2   4  0  13
 403  24 241   6  60  0  90
  80   1  10  12  17  0   6
 122   0   6   3  86  0   9
 124   1  21   4   5  1  48
 303   1  17   2  31  0 234
```

There were 4,276 user-state tokens. Non-O micro precision/recall/F1: 0.5282/0.2606/0.3490; macro: 0.5567/0.2046/0.2512. Gold O share 0.4696; predicted O share 0.7383. Mixed: 2,658 tokens, micro F1 0.3430, macro F1 0.2550. English: 1,618 tokens, micro F1 0.3557, macro F1 0.2371. Both slice matrices are in JSON.

| Label | Support | Predicted | TP | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| B-TRACK | 300 | 46 | 17 | 0.3696 | 0.0567 | 0.0983 |
| I-TRACK | 824 | 386 | 241 | 0.6244 | 0.2925 | 0.3983 |
| B-ARTIST | 126 | 29 | 12 | 0.4138 | 0.0952 | 0.1548 |
| I-ARTIST | 226 | 211 | 86 | 0.4076 | 0.3805 | 0.3936 |
| B-ALBUM | 204 | 1 | 1 | 1.0000 | 0.0049 | 0.0098 |
| I-ALBUM | 588 | 446 | 234 | 0.5247 | 0.3980 | 0.4526 |

Exact 218-case TRACK failure taxonomy: labels absent 96; orphan I only 104; multiple B/spans 10; broken/discontinuous B 8; invalid selected offset 0; selected optional conflict 0; forbidden/empty after tightening 0; other decoder rejection 0. Categories are exclusive and exhaustive with no unclassified case. Across all 300 plays: any TRACK signal 180, orphan I 159, zero B 258, one B 38, multiple B 4, one contiguous run 126, multiple runs 54, structurally valid TRACK 19, signal but structurally invalid 161, S3 emitted TRACK 12 (3 exact, 9 non-exact). Mixed: signal 123, structurally valid 18, S3 emitted 11/exact 3. English: signal 57, structurally valid 1, S3 emitted 1/exact 0.

Typed uses argmax. Gold play: 230/300 typed play, 70/300 typed not-play; play probability mean 0.5722, median 0.5697, range 0.2682–0.7868, signed logit margin mean 0.3053. Gold unknown: 162/240 typed play, 78/240 typed not-play; play probability mean 0.5442, median 0.5378, range 0.2939–0.8008, signed margin mean 0.1881. Full p05–p95 and near-boundary buckets are in JSON. The typed×TRACK matrix on 300 plays is typed-play: 12 structurally valid / 218 invalid-or-missing; typed-not-play: 7 valid / 63 invalid-or-missing. Under the diagnostic-only typed bypass, 7/70 have structurally valid TRACK, 3 exact TRACK, and 1 full semantic exact; 63/70 remain invalid or missing. Actual validity gate blocks none of those 7. This counterfactual did not run another forward or alter decisions.

Validity probability is near constant: gold-play mean 0.617948, gold-unknown mean 0.618212, mean gap -0.000265, pooled range 0.004757, descriptive AUROC 0.4310. Every play and unknown score was at or above 0.5. Mixed AUROC 0.4985; English AUROC 0.3081. This is descriptive evidence of weak separation, not a calibration or threshold-tuning result.

Raw optional BIO on gold-present rows: ARTIST 126 rows, 38 all-O, 67 with any correct token, 12 correct B, 7 exact gold BIO sequences, 13 structurally valid if TRACK ignored, 5 exact if TRACK ignored. Mixed ARTIST 30 rows / 6 correct B / 5 structurally valid; English 96 / 6 / 8. ALBUM 204 rows, 45 all-O, 131 with any correct token, 1 correct B, 0 exact gold BIO sequences and 0 structurally valid if TRACK ignored. Mixed ALBUM 108 rows / 1 correct B / 0 structurally valid; English 96 / 0 / 0. The JSON retains wrong-slot and partial-I counts.

Decoder interaction: 96 failed rows have no TRACK signal; 168 have signal but S3 emits no TRACK. In the 218-case failure set, 112 have a minor BIO grammar defect and 122 meet strict grammar/selected-conflict rejection, the latter requiring a hypothetical repair. These are descriptive counts; no decoder repair was implemented.

## Boundaries and next gate

All six persistent flags remain false: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, and `LOCAL_AI_FALLBACK_APPROVED`. No training, backward, optimizer, scheduler, threshold sweep, decoder change, app wiring, held-out, Stage A, or quality promotion occurred. Issue #68 stays open; Issues #80/#82 are unchanged. PR #92 remains open and unmerged for independent review. Any adaptation or repair requires a separate decision and authorization.
