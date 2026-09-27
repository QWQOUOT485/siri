# PR #79 checkpoint / verified S3 validation-only diagnostic — 2026-09-27

**Current result: `LAYA_PR79_S3_DIAGNOSTIC_NEW_BLOCKER` — `FileNotFoundError` during the base-model load attempt.**

**NON_ACCEPTANCE_DIAGNOSTIC_ONLY.** No validation prediction was produced. Historical reproduction and S3 quality/safety comparison are **not run**, not zero-quality measurements. No retry occurred.

## Scope, reviewed state and execution order

- Exact main/base: `6c1373dd9e7985616a76042756e7da2ddad16ade`.
- Branch: `codex/stage-b-laya-s3-pr79-validation-diagnostic`.
- PR #85 reviewed head `d2c240982d04a9fd1793c5607a5831dc187a527b` is merged at the exact base above. `laya-s3-research-v1` remains accepted.
- Pre-live frozen commit: `2c3cf20bdce746776d83c3a336312eca289b1a4a`.
- Diagnostic runner SHA-256: `4b259bd9629628aeb3d25ad231521a745cfec81ac0ea6ce6786386259ef94b4f`.
- Task-scoped authorization: `pr79-checkpoint-s3-validation-diagnostic-v1`. It authorized one diagnostic invocation, no training or subsequent execution.
- No-compute preflight passed; checkpoint bytes/read-only/non-redirected identity checked without `torch.load`. Synthetic focused suites passed **343 tests**, one durable-result test skipped before execution. Tokenizer-only equivalence passed **540/540** before live.
- Independent pre-live review verified the final source, seven historical hashes, exact base, clean commit, checkpoint identity and absent durable result. One live invocation followed that review. No runner or test behavior was changed after the invocation.
- [Sanitized structured result](LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json), canonical SHA-256: `ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd`.

## Observed blocker and limits of diagnosis

The child completed identity checks, validation eligibility/rendering, GPU selection, and the strict base-state header check. It incremented `model_loads` immediately before `laya.load(...)`, which raised `FileNotFoundError`. The counter is therefore **one attempted load, zero completed loads**. The result has no `residency` or completed model-load timing, and no checkpoint load or validation forward was reached.

Only the exception class was retained. The child did not persist a traceback or missing path; the parent stderr is empty. The exact missing file and cause remain **unknown**. The read-only guard recorded **284 rejected write probes**, but the available evidence does not establish that those probes caused this exception. No model re-instantiation or diagnostic retry was used to investigate it.

The smallest next gate is a separately authorized, narrowly instrumented load diagnostic that preserves read-only/data boundaries and records a sanitized failing path/stage. Review that evidence before authorizing any further validation. There is no measured failure decomposition from which to recommend adaptation. Full head-only adaptation remains unauthorized.

## Execution counts

| Operation | Actual result |
| --- | --- |
| Live invocations | 1 |
| Base model load attempts / completed loads | 1 / 0 |
| Research checkpoint loads | 0 |
| Validation dataset inference passes | 0 |
| Validation forward batches | 0 of planned 34 |
| Shared decisions / historical decoder calls / S3 calls | 0 / 0 / 0 |
| Additional model forwards for second decoder | 0 |
| Optimizers constructed / training steps / backward calls | 0 / 0 / 0 |
| CPU fallback | false; no successful model residency claim |

The frozen source has one `laya.load`, one CPU/`weights_only=True` `torch.load`, and one `historical.forward` call site in the fixed 34-batch loop. The loop would use 33 batches of 16 plus 12, eval/no-grad and PR #79 BF16 forward. Shared typed/probability/validity/BIO values are dispatched to the immutable historical decoder and `research.validation_decode`. Synthetic tests exercise real S3 dispatch and masking. These are **source/test evidence only** because live execution stopped before these paths ran.

## Checkpoint and restoration

Checkpoint: `<external-adaptation-root>/6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a/final.pt` (canonical external root `D:\ai\ai\stage_b_small_adaptation`).

- SHA before = after: `199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d`.
- Size before = after: **177394599 bytes**.
- Read-only before = after: **true**; file and every ancestor non-symlink/non-junction/non-reparse.
- Reviewed expected schema `laya-small-adaptation-final-v1`, completed steps **189**, no frozen weights. **This task did not deserialize the payload, so live schema/binding/restore validation was not reached.**
- Source validation checks exact seven-key payload/schema/step/binding and restores only typed/span/validity groups. Optimizer payload is not used; no optimizer is instantiated. Binding is the historical normalized config + seed + exact selection manifest + historical identities.
- Restored and post-validation parameter hashes: **not obtained**. The reviewed expected hashes remain in the runner and PR #79 evidence; they are not claimed as observed restore results here.
- Checkpoint never modified, chmodded, replaced or removed; retained read-only as before.

## Source and artifact immutability

All seven historical/reviewed hashes below are exact before = after; the new runner is also source-bound in the canonical record.

| Historical/reviewed source | Before = after SHA-256 |
| --- | --- |
| `local_ai_stage_b_laya_adapter.py` | `cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e` |
| `local_ai_stage_b_laya_s3_research.py` | `b01a254db9bfb1d84023c0f9d88ff7d49ccb789ff7888961ea7e000dfa2d4388` |
| `local_ai_stage_b_laya_small_adaptation.py` | `85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e` |
| `local_ai_stage_b_laya_span_decoder.py` | `f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845` |
| `local_ai_stage_b_laya_span_representability_audit.py` | `6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087` |
| `local_ai_stage_b_laya_span_seam_design.py` | `7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72` |
| `local_ai_stage_b_laya_span_seam_implementation_verify.py` | `35203544303153cab0df03145bddb21a6c6f08f0d97f5b4f213cedfab115c3e2` |

Accepted PR #79 canonical JSON SHA remains `4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8`. Its JSON byte SHA is `739fc9e2e840f16494eb5655390afd563316626860bf6078c32213d997fe0424`; report byte SHA is `4d2b2b1710269bf795f0a7873596576df21cb1fb0fbec186e83ecc5fedd02691`. Both are unchanged. No accepted PR #79 metric/report was edited, replaced or rescored.

Reviewed PR #84 canonical `08e8173175f5a879b7677cde2fdaedbc844ae5e4dc790b1d81bb174c46d4bcbb` and PR #85 canonical `38bdead38e5dea83cf45e522279e7280fdfa0aeb08d8d6e12984cff1d7591d87` were verified before and after.

Model/source/runtime before = after:

| Identity | Value |
| --- | --- |
| Laya clean source revision | `42626c348753fbb17572a813127df2278a1ec527` |
| Model/tokenizer revision | `052592a15d198d9ad47da779604259b10b47b7aa` |
| Full model aggregate, recomputed both times | `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf` |
| Primary weight SHA | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| Tokenizer JSON | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` |
| Tokenizer config | `2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f` |
| Laya config | `25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6` |
| Qualified venv inventory | `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337` |

The model aggregate includes all 11 canonical files. Strict base-state header: 170 tensor keys, 321908995 parameter elements, 321908998 state elements. Header/hash evidence does not prove successful model load.

## Validation and process boundary

Validation SHA before = after: `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a`. Exact **600 rows / 100 six-row groups / 300 supported play / 240 supported unknown / 60 blocked**. The 60 deterministic/safety rows were filtered before rendering. All **540 eligible renderings** matched pinned upstream build_sequence; their IDs and the 60 blocked IDs are in JSON. This proves data/rendering gates, not inference.

Only `validation` row content was opened by the live child. Train, held-out, sealed held-out and Stage A rows were not opened. No old full-corpus/seal/preflight function was called. Historical selection/identity metadata came from committed sanitized evidence, not train rows.

Qualified Python `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe`, Python **3.14.7**, `-B -X utf8`; raw-byte subprocess transport; HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1; PYTHONPATH scrubbed. Torch **2.13.0+rocm10.0.0**, HIP **7.15.26333**, transformers **4.57.6**, safetensors **0.7.0**, huggingface-hub **0.36.2**, numpy **2.3.5**.

Python filesystem write/network operations are denied. Existing-directory `mkdir` attempts are permitted only because they cannot create a directory; actual creation/write attempts are denied. The existing Inductor cache path is supplied only in the child environment. Import-only pre-live checks observed 142 caught dependency write probes; the actual invocation recorded 284 denied writes, with no allowed writes and no network/protected-row events. No global settings or dependencies changed. Python audit evidence is not a claim about unobservable native-library filesystem operations.

Full regression tests outside the live child use existing fixture/integrity mechanisms and may read train/held-out/Stage A fixtures as normal CPU tests. Those are distinct from this diagnostic's validation-only model-input boundary. No quality benchmark was rerun.

## Device, runtime and unavailable comparison

Enumerated target **cuda:1 / AMD Radeon RX 9070 XT / gfx1201 / 17095983104 bytes**; visible iGPU **cuda:0 / AMD Radeon(TM) Graphics / gfx1036 / 13064830976 bytes**. Current-device check passed; no alternate GPU or fallback selected.

Baseline VRAM allocated/reserved/peak allocated/peak reserved: **0 / 0 / 0 / 0 bytes**. After-load/restore/validation/final VRAM and model/checkpoint/validation timings were not reached. No throughput or batch-1 latency conclusion.

| Requested diagnostic result | Availability |
| --- | --- |
| Historical 540/540 reproduction and exact aggregate comparison | Not run |
| Historical/S3 metric tables and mixed/en slices | No new model output |
| S3 safety gate | Not run; no safety-pass claim |
| 540-row transition matrix | Not run |
| 300-play failure decomposition | Not run |
| TRACK/optional presence, exactness and delta histograms | Not run |
| 11 historical play cross-reference | Not run |
| Learned exact vs structural oracle gaps | Not measurable |

The reviewed gold-BIO structural ceilings remain TRACK297/300, ARTIST126/126, ALBUM203/204. They are structural reference evidence, not learned results from this task. If the diagnostic had completed, exact prediction objects and all quality aggregates/slices would have been gated; uncalibrated confidence-summary equality is reported separately, not an added acceptance condition.

## Authority and remaining gates

All six persistent flags were checked in the active environment and remain false: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, `LOCAL_AI_FALLBACK_APPROVED`.

No optimizer, backward, training, checkpoint mutation, validation tuning, second live invocation, held-out/Stage A model input, app wiring, production fallback, semantic memory or model-quality acceptance. Issue #68 stays OPEN. Issues #80/#82 are unchanged. The diagnostic PR stays OPEN/UNMERGED for independent review.

## Verification

- Focused Laya/decoder/verifier-design-audit/research/load/shape/pipeline/hardware suites: **344 passed** after the recorded blocker, including durable canonical/source/count checks. Pre-live343 passed +1 expected skipped artifact test.
- Full unit suite: **956 passed**, two existing dependency deprecation warnings,274.26 seconds.
- Windows integration: **5 passed**. This is the existing integration suite, not Siri/Spotify client E2E acceptance.
- Qualified Python `-B -X utf8` used throughout. CPU pytest appends the existing ordinary-project site-packages read-only; that addition is never propagated into the live child.
- `python -m compileall -q app scripts tests`: passed.
- `git diff --check`: passed; Markdown relative links: **26 checked**, all resolved.
- Seven historical/reviewed sources and PR #79 evidence unchanged; zero diff under `app/`, frozen `artifacts/`, and `tests/fixtures/`.
- Primary worktree's PROJECT_STATUS/Shortcut/ShortcutV2 hashes unchanged: `968907d1545ade5fe7be6e4958af2ccc23781a9f138fbfe1deae5bddb8e864bc`, `31a6ffc09aa25a819b506157cc847c0482bb72eff96827a5bc8fc9e76e259c89`, `934a932464238ff3594ad90f36c4934b95a7b8b3ce59737dcc785484b01e1484`.
- Issues #80/#82 title/body/state/comments/updatedAt equal read-only pre-task snapshots. Issue #68 current section records this blocker and corrects PR #85 to merged, preserving reviewed history.

No further model execution is permitted in this task.
