# Stage B v6 Candidate Freeze — Carrier Naturalness Correction

This is an offline, unsplit candidate and review pool, **pending independent
semantic review**. Main `75a94cb1f081e0fa0a25f5571b85dafc05d6eb18` contains
the v5 pool from PR #55. External Gemini 3.8 High returned 3,600 v5 accepts,
but gatekeeper review found at least 210 systematic carrier-naturalness misses.
Those external decisions were **not imported** into either review directory.
V4 and v5 artifacts remain historical audit evidence.

## Carrier audit and corrections

The audit inspected the generator-owned wording of every one of the 32
families, separately from fictional entity names. Eleven families have a
documented carrier defect and all their rows received a new utterance. The
remaining 21 families retain their v5 utterances. Candidate IDs remain stable,
while source and record hashes changed across the entire v6 pool because the
generator version changed.

| Family | Rows | Rephrased | Carrier finding |
| --- | ---: | ---: | --- |
| `play_en_asr_spacing` | 66 | 66 | `Play this request` and bare field labels were generator instructions, not plausible speech. |
| `play_hant_particle` | 120 | 120 | `演出者標籤` / `專輯標籤` were database labels. |
| `play_hans_particle` | 24 | 24 | `演出者标签` / `专辑标签` were database labels. |
| `play_en_direct` | 66 | 66 | `this requested track` described the task rather than a user's request. |
| `play_en_conversational` | 66 | 66 | `this selected song` implied a prior selection absent from the utterance. |
| `play_en_polite` | 66 | 66 | `the requested song` used instruction-template wording. |
| `play_mixed_conversational` | 90 | 90 | `artist 是` / `album 是` were field labels. |
| `play_mixed_word_order` | 90 | 90 | `album 是` / `artist 是` and leading `album` were field labels. |
| `play_mixed_particle` | 90 | 90 | `album` was a field label in otherwise conversational wording. |
| `play_mixed_asr_case` | 90 | 90 | `artist` / `album` were field labels, not ASR case variation. |
| `play_mixed_asr_spacing` | 90 | 90 | `artist` / `album` were field labels, not ASR spacing variation. |
| `play_en_punctuation_loss`, `play_en_word_order` | 132 | 0 | Spoken `by` / `from` slot carriers retained. |
| `play_hant_direct`, `play_hant_conversational`, `play_hant_word_order`, `play_hant_homophone`, `play_hant_spacing` | 600 | 0 | No clear carrier-level defect; telegraphic spacing form is a plausible short voice request. |
| `play_hans_direct`, `play_hans_conversational`, `play_hans_word_order`, `play_hans_homophone`, `play_hans_spacing` | 120 | 0 | Same assessment in Simplified Chinese. |
| `play_mixed_code_switch` | 90 | 0 | Natural `by` / `from` code switching retained. |
| `unknown_artist_only`, `unknown_missing_track`, `unknown_unresolved_reference`, `unknown_ambiguous_version`, `unknown_unsupported_domain` | 1,380 | 0 | Existing negative carriers remain semantically explicit under the frozen label contract. |
| `deterministic_playback_control`, `deterministic_app_control` | 180 | 0 | Deterministic pre-model controls retained. |
| `safety_hostile_text` | 240 | 0 | Hostile/system-like carrier and pre-model block retained. |

Representative old → new utterances (entity surfaces held fixed):

| Family | v5 | v6 |
| --- | --- | --- |
| English ASR spacing | `Play this request PapersideLanternsline artist Northlight album The Long Way Home please` | `listen to PapersideLanternsline by Northlight off the album The Long Way Home please` |
| Traditional particle | `想聽歌名是未央，演出者標籤是星河樂團，專輯標籤是遠方，就這首就好` | `想聽未央，星河樂團唱的，收錄在遠方，就這首` |
| Simplified particle | `想听歌名是未央，演出者标签是星河乐团，专辑标签是远方，就这首就好` | `想听未央，星河乐团唱的，收录在远方，就这首` |
| English direct | `Play this requested track: Paperside Lanternsline by Northlight from The Long Way Home` | `Play Paperside Lanternsline by Northlight from The Long Way Home` |
| English conversational | `Listen to this selected song: Paperside Lanternsline by Northlight from The Long Way Home` | `Listen to Paperside Lanternsline by Northlight from The Long Way Home for a bit` |
| English polite | `Play the requested song Paperside Lanternsline from The Long Way Home by Northlight for me` | `Play Paperside Lanternsline from The Long Way Home by Northlight when you have a moment` |
| Mixed conversational | `我要聽：Cobaltside Lettersline，artist 是 Mosaic，album 是 The Civic Way Home` | `我要聽 Cobaltside Lettersline，Mosaic 唱的，收錄在 The Civic Way Home` |
| Mixed word order | `Play 一下這首歌：Cobaltside Lettersline，album 是 The Civic Way Home，artist 是 Mosaic` | `Play 一下 The Civic Way Home 裡的 Cobaltside Lettersline，by Mosaic` |
| Mixed particle | `聽這首歌，請幫我找：Cobaltside Lettersline，by Mosaic，album The Civic Way Home` | `想聽 Cobaltside Lettersline 這首，by Mosaic，收錄在 The Civic Way Home，謝謝` |
| Mixed ASR case | `請播放這首音樂給我 cobaltside lettersline，artist Mosaic，album The Civic Way Home` | `請播放這首英文歌 cobaltside lettersline，by Mosaic，在 The Civic Way Home 這張專輯裡` |
| Mixed ASR spacing | `Put on 這首音樂：CobaltsideLettersline，artist Mosaic，album The Civic Way Home` | `想聽聽 CobaltsideLettersline，Mosaic 的歌，The Civic Way Home 那張 album 裡的，謝謝` |

English ASR variant 5 still applies one bounded spacing corruption to the
track surface only; artist and album spans remain exact. All four optional
artist/album modes are retained. The independent zh-Hans inventory is v2
because the natural particle now uses `唱`. Its reviewed allowed-Han set is
versioned, hashed, and separate from the generation conversion map. Unknown
Han characters still fail closed, including unmapped Traditional-only `龍`;
`沿著之前` remains invalid as zh-Hans.

## Offline validation

| Check | v6 result |
| --- | ---: |
| Rows / source groups / families | 3,600 / 600 / 32 |
| Supported play / supported unknown / deterministic-only / safety-only | 1,800 / 1,260 / 300 / 240 |
| zh-Hant / zh-Hans / mixed / en | 1,380 / 288 / 1,140 / 792 |
| Artist present / absent; album present / absent | 1,080 / 720; 1,080 / 720 |
| Both optional slots / neither | 720 / 360 |
| Play span errors / optional-slot status errors | 0 / 0 |
| Stage A leakage | 0 |
| Exact duplicates / same-group near duplicates | 0 / 0 |
| Cross-group near duplicates / cross-group exact duplicates | 0 / 0 |
| Production eligible supported play / unknown | 1,800 / 1,260 |
| Production blocked deterministic-only / safety-only | 300 / 240 |
| Production scope mismatches | 0 |
| zh-Hans script validation / `著` rows | passed / 0 |
| v4 residuals: English delimiter, compound volume, bare missing track, duplicated shell verb | 0 / 0 / 0 / 0 |
| v5 residuals: English ASR meta, Traditional meta, Simplified meta | 0 / 0 / 0 |
| Additional English meta / mixed field-label residuals | 0 / 0 |

Stage A identity is
`60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`
(109 test-only cases). The near-duplicate config identity remains
`64045462fe025b66dd5346df1e1d80cc886ab5e1fb1e8495fa57fe9aa9eb6ae7`.
Neither protocol nor production gate changed. English and mixed catalogs
retain 1/2/3/4+ word entity buckets plus digit, apostrophe, hyphen, period,
parenthesis, and punctuation diversity. The unchanged entity catalog has the
same file SHA as v5 because its bytes did not change; no changed artifact
reuses a v5 hash.

The review manifest reports 12 packets of 300, exact-once coverage, and
`packets_are_not_splits=true`. Initial state: `decision_count=0`, `reviewed=0`,
`accepted=0`, `rejected=0`, `needs_correction=0`, `conflict=0`, `pending=3600`.
All 3,600 candidate record hashes differ from v5 and bind to their v6 rows.
A v5 packet decision is rejected by the v6 validator.

The focused candidate/review suite passed **55 tests**. The full unit suite
passed **559 tests** with 2 existing dependency deprecation warnings.
`python -m compileall -q app scripts tests` and `git diff --check` passed.
These mechanical checks do not constitute independent semantic acceptance.

## Frozen file SHA-256

These are SHA-256 hashes of file bytes, distinct from canonical JSON source
identities inside the manifests. The review loader pins canonical source
identities: corpus `a5671cbd8c3b28c3d14994786b800b70797aac19d0392931fa3f8c29e9628d0d`,
catalog `7b0a09825cb40e046a7c27cc4f51f08aa22d42e5a5587c23710f831c3c0f15cb`,
config `132398500823674d3fec24361139145247f92b13a17cd7476e40110d4ac7df2e`,
and manifest `13e50c4ccc336cc46c62d9a45654d2783d981dbcad0ea807869a9379d4fe3e18`.

| v6 artifact | File SHA-256 |
| --- | --- |
| `candidate_corpus.jsonl` | `2e8ff010219d2de3a3c8e95339568daaa5dec8faf5032457cf81acf30839a297` |
| `entity_catalog.json` | `2b91ba5f2683813c0839530c0778351250e3b0854f12bc853ebe60e78e7123a7` |
| `generator_config.json` | `7bd0e0b1f1d86c421367dd65b9e72f6d2108255501c07a1c14e1cf87853e1bf1` |
| `candidate_manifest.json` | `2a73237ba3d7115204244c878b9e3ab81f3006641859b0b8dc2ea80cb62eccfb` |
| `candidate_review_queue.jsonl` | `43da514baf87fc323361fb3b9a71960b9b8ea030ae669d76d8bcc8f36a82e6e2` |
| `review/review_manifest.json` | `0a65838a5dec5f9db982021c92dbc82e34a94d3a205d0f88de206b1874a6216d` |
| `review/decisions/README.md` | `71235b5ba46fa1fee1498e08048eb42b5e7fc8f844fecc1970fde5f8b581fc53` |
| `scripts/data/stage_b_zh_hans_script_inventory_v2.json` | `f41fdf94c099048b02039bb647044ffca0d0482bb983a6c6d00dd3e68938654d` |
| `review/packets/packet-01.jsonl` | `cf77c8ca783fe8919fcc364ce96d6be1e4325088f13991225b94eef290cc7f1a` |
| `review/packets/packet-02.jsonl` | `95e0b1632603bb4bc4f75485074a80b92c04b9427ba728015c4764e7e85af351` |
| `review/packets/packet-03.jsonl` | `00d48b7b2e8e58e56fc4766bfa36f8fac44e4d57d7e64242cf239e7f78278b05` |
| `review/packets/packet-04.jsonl` | `03a46b9b0292fb6c6e0c95c37b43a258490dfa69276a30f76aabcc0c46484958` |
| `review/packets/packet-05.jsonl` | `5794840b798ae85d1b728b80276194d59acc91eba7e16d5614f20fcfb3ad12da` |
| `review/packets/packet-06.jsonl` | `0ea636fc78d85692c111c25859e307adfaed487a73f6abd5d126f813db55a313` |
| `review/packets/packet-07.jsonl` | `b384e8563e8a757b1b48d59cdbe118765bfd477c3791ffae7e34cb3854326cf0` |
| `review/packets/packet-08.jsonl` | `3ab843bd448824a3ea673e7543546dda1ba5e23626ef37369b61bd8e86c24ec0` |
| `review/packets/packet-09.jsonl` | `1851bd42365b7ff55f666153ee9c6e54874caa6b965635c78425397e942ecd3e` |
| `review/packets/packet-10.jsonl` | `ba845a2c822f1f628c6d983a371546ff4aff7e3ec961393ac4fae64e379921fe` |
| `review/packets/packet-11.jsonl` | `5a8b0cd98fa699b5edf1abf3f704077881f5f3217cac1ede4a56635f23ea4062` |
| `review/packets/packet-12.jsonl` | `7f93fb0ad96b35d008f1480e749649d4b927f1c846e94753eae407831e164685` |

No final 3,000 selection, split, held-out seal, training, model compute,
benchmark promotion, Semantic Memory, or Local AI production fallback was
performed or approved. `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false` remain the required settings.
