# Stage B v6 Candidate Freeze — Carrier Naturalness Correction

This is an offline, unsplit candidate and review pool, **pending independent
semantic review**. Main `75a94cb1f081e0fa0a25f5571b85dafc05d6eb18` contains
the v5 pool from PR #55. External Gemini 3.8 High returned 3,600 v5 accepts,
but gatekeeper review found at least 210 systematic carrier-naturalness misses.
Those external decisions were **not imported** into either review directory.
V4 and v5 artifacts remain historical audit evidence.

PR #56 gatekeeper inspection at exact head
`f269a90401fb66ecb277927b88bfa0713879c3e8` found a dangling album
modifier in 54 `play_mixed_asr_spacing` rows. This follow-up changes only
those album-present utterances, then regenerates source-bound v6 artifacts.
PR #56 remains pending gatekeeper re-review and independent semantic review.

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
| `play_mixed_asr_spacing` | 90 | 90 from v5; 54 further corrected at reviewed PR head | `artist` / `album` were field labels in v5; the reviewed v6 album carrier ended with a dangling `裡的`. |
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
| Mixed ASR spacing | `Put on 這首音樂：CobaltsideLettersline，artist Mosaic，album The Civic Way Home` | `想聽聽 CobaltsideLettersline，Mosaic 的歌，收錄在 The Civic Way Home 這張專輯裡，謝謝` |

For the gatekeeper follow-up, the reviewed v6 carrier
`想聽聽 <TRACK>，<ALBUM> 那張 album 裡的，謝謝` (or the same with
`<ARTIST> 的歌`) became
`想聽聽 <TRACK>，收錄在 <ALBUM> 這張專輯裡，謝謝` (or the
same with `<ARTIST> 的歌`). The two album-absent shapes remain text-identical.
The family has 90 rows: artist absent/album present 18, artist present/album
absent 18, both present 36, both absent 18. Exactly 54 album-present
utterances changed against the reviewed head. Candidate IDs and all other
row text are unchanged: the other 36 family rows and 3,510 other-family rows
are byte-for-byte identical at the utterance level. Entity catalog bytes,
v4/v5 artifacts, Stage A fixtures, runtime code, and the near-duplicate
protocol did not change.

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
| v6 dangling mixed ASR-spacing album carrier residual | 0 |

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

The focused candidate-generator suite passed **32 tests**, and the focused
independent-review suite passed **25 tests**. The full unit suite passed
**561 tests** with 2 existing dependency deprecation warnings.
`python -m compileall -q app scripts tests` and `git diff --check` passed.
These mechanical checks do not constitute independent semantic acceptance.

## Frozen file SHA-256

These are SHA-256 hashes of file bytes, distinct from canonical JSON source
identities inside the manifests. The review loader pins canonical source
identities: corpus `fec537e73e45b4af68ad15bb9e75e09c0f3c2780fcf179a4dd8a3f0dc37a6238`,
catalog `7b0a09825cb40e046a7c27cc4f51f08aa22d42e5a5587c23710f831c3c0f15cb`,
config `132398500823674d3fec24361139145247f92b13a17cd7476e40110d4ac7df2e`,
and manifest `83e27d68f13821839278957b8bc5291ef18091ed135319670da5fd139612bea6`.

| v6 artifact | File SHA-256 |
| --- | --- |
| `candidate_corpus.jsonl` | `dc6063d20d9c60b8dba1bf26841f32730fbc7d07114a877f2f615b335c5b209a` |
| `entity_catalog.json` | `2b91ba5f2683813c0839530c0778351250e3b0854f12bc853ebe60e78e7123a7` |
| `generator_config.json` | `7bd0e0b1f1d86c421367dd65b9e72f6d2108255501c07a1c14e1cf87853e1bf1` |
| `candidate_manifest.json` | `e46a9312fb4c28662c45c06092b19832a7e7efc52f3589975e9fa2e0dacda7fb` |
| `candidate_review_queue.jsonl` | `b61ebda63ae974058ee6358dbd89b64ccfaeadf88e9a4ef67ab61c1cf6f8790e` |
| `review/review_manifest.json` | `5145910e0e7cd447f8cd14dfd335b51389e6b2d09bbd4a568bfacd6fcee75afc` |
| `review/decisions/README.md` | `71235b5ba46fa1fee1498e08048eb42b5e7fc8f844fecc1970fde5f8b581fc53` |
| `scripts/data/stage_b_zh_hans_script_inventory_v2.json` | `f41fdf94c099048b02039bb647044ffca0d0482bb983a6c6d00dd3e68938654d` |
| `review/packets/packet-01.jsonl` | `66732c2dbac4df60eb3529cf768dda50fd0024ffd797033a2f45601e25f46b10` |
| `review/packets/packet-02.jsonl` | `747bb6dd96bd18e67b8d3506f66312418c575d2c8db3a8f921c0517c7c23b4cb` |
| `review/packets/packet-03.jsonl` | `c65fdb08d9d1c0cfa4a1a3eb9bfd1c33ab6c32d29efa3136a5cdcd0b87a7f855` |
| `review/packets/packet-04.jsonl` | `a80c4e36c22396dd737fd92d84255a986351c74de6702bff20680503bf8642e7` |
| `review/packets/packet-05.jsonl` | `2593fade44d348adc4bccb2214a2321793715f6cdb9667beee721324c46336fa` |
| `review/packets/packet-06.jsonl` | `46e7670a009f486064bdf72d4560e992a081719d13ea99ef4f04a973af3ecfe8` |
| `review/packets/packet-07.jsonl` | `e6501834c37d586476003148701df1f19a72be1ad6d2fbfacf1c5b7128a7a24a` |
| `review/packets/packet-08.jsonl` | `0f20b13b845f2806efe86c4873ba3b3f14aa07c0d0b1698181a0d43c879b3483` |
| `review/packets/packet-09.jsonl` | `c75382634a72607ba9e460c5ca18f229a9c826efc273207523fc895621971a89` |
| `review/packets/packet-10.jsonl` | `f889effdc8bd152b56de8d6dad3897688add4d5af1475b4bf50104216e42eb9b` |
| `review/packets/packet-11.jsonl` | `289df7227ea2d4bef08dead545706dcbc71ea06029a337a8e6b6134257370d28` |
| `review/packets/packet-12.jsonl` | `760e419b759aebbc964ad669f45fc166cc98e550d6fb9c559afde3ee89819f0e` |

No final 3,000 selection, split, held-out seal, training, model compute,
benchmark promotion, Semantic Memory, or Local AI production fallback was
performed or approved. `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false` remain the required settings.
