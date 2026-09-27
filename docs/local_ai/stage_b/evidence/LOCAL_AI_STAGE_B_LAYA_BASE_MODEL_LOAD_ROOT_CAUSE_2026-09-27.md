# Laya base-model load root-cause diagnostic — 2026-09-27

**Result: `LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_DIAGNOSTIC_PASSED`.**

One base-model load completed on the exact RX 9070 XT under scratch-only filesystem writes. No checkpoint, dataset, forward, validation or training was executed. This is load/residency diagnostic evidence, not model-quality evidence.

## Reviewed state and task boundary

- Exact main/base: `fcb378031e2befff1ba7477952041647a5b8cc4a`.
- Branch: `codex/stage-b-laya-load-guard-root-cause`.
- PR #86 reviewed head `deb074e5a9c4390ab8c4c77f40e4d7337d2f4a5a` is merged at this base. Its blocker remains historical evidence: `FileNotFoundError`, canonical SHA `ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd`, 284 denied writes.
- Frozen pre-live commit: `13c7ba5cdfddd208fa493bcd61756ef5a9af615c`.
- Executed runner SHA: `5e82645ec396509155fcb85d9d24989729be84ce81b08e550e32e5a3098f163e`.
- Task-scoped authorization: `laya-base-load-guard-root-cause-v1`.
- Independent pre-live review covered guard boundaries, restore-free/no-data source paths, sanitized exceptions, one-load counter, transport failures and clean base-to-head whitespace check. After review, runner/tests were frozen, byte hash rechecked and one invocation dispatched. No runner/test changes or retries followed.
- [Sanitized JSON](LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_2026-09-27.json), canonical SHA: `962b0f0b720fd87cb21b7a22cadc228150733327e2dfcc318628de28194f5535`.

## Finding and its limit

The exact pinned load now succeeds with protected identities unchanged. During `laya_load`, the audit observed a temporary file write/delete, then a filelock-style `probe-source` creation, link and cleanup, all inside the task scratch namespace. This supplies direct evidence of normal dependency temporary filesystem behavior during model construction.

The frozen automated finding is **`pr86_global_write_guard_regression_supported=false`**. Its predeclared conservative predicate requires a successful unchanged load, write-open events, **and a nonempty scratch file surviving dependency shutdown**. The dependencies removed their temporary files, leaving an empty file inventory, so that last condition was false. This flag is preserved exactly; it was not changed after observing the result.

The successful scratch-enabled load and temporary-write event chain are consistent with the proposed blanket-guard regression. They do **not conclusively connect the specific PR #86 FileNotFoundError to a particular denied operation**, because PR #86 retained neither a failing path nor traceback. No claim of proven causation is made. No quality or historical-vs-S3 comparison exists yet.

## Counts and load readback

| Operation | Actual |
| --- | --- |
| Live invocations | 1 |
| `laya.load` attempts / completed | 1 / 1 |
| Adaptation checkpoint loads | 0 |
| Dataset passes / model forward calls | 0 / 0 |
| Training steps / backward calls | 0 / 0 |
| Optimizer / scheduler constructed | false / false |
| Exception / transport failure | none / none |
| Load duration | 16.197933399998874 seconds |

The exact call is `laya.load(str(pinned.MODEL), device="cuda:1")`. No manual model substitute, project-owned heads or second load. Agent deletion occurred after successful PR #72-contract readback.

| Readback | Actual |
| --- | --- |
| Selected / Laya-reported device | `cuda:1` / `cuda:1` |
| GPU | AMD Radeon RX 9070 XT / gfx1201 / 17095983104 bytes |
| Other visible device | cuda:0, AMD Radeon(TM) Graphics / gfx1036 / 13064830976 bytes |
| Parameter devices / buffer devices | cuda:1 / cuda:1 |
| Parameter elements | 321908995 |
| Constructor parameters marked requires_grad | 321908995; no backward or training performed |
| Persistent buffer | temperature, 3 elements |
| State elements | 321908998; keys match parameters plus persistent buffers |
| Parameter / buffer dtype sets | torch.float32 / torch.float32 |
| Base weight compatibility | strict_load_state_dict_succeeded |
| CPU fallback | false |

| VRAM phase | Allocated bytes | Reserved bytes | Peak allocated | Peak reserved |
| --- | --- | --- | --- | --- |
| Baseline | 0 | 0 | 0 | 0 |
| After load / peak | 1307833856 | 1333788672 | 1307833856 | 1333788672 |

This is not batch-1 latency or inference precision qualification; Issue #80 is unchanged.

## Scratch and filesystem policy

The parent created the previously absent task namespace `D:\ai\ai\stage_b_laya_load_diagnostic\guard-regression-v1` outside repository, canonical model/source, checkpoint and frozen-data roots. No pre-existing user data was removed. The live child received only category-relative bindings in durable evidence:

| Child-local variable | Relative to diagnostic scratch |
| --- | --- |
| TMP / TEMP / TMPDIR | tmp |
| TORCHINDUCTOR_CACHE_DIR | torchinductor |
| TRITON_CACHE_DIR | triton |
| HF_HOME | hf |
| HF_HUB_CACHE | hf/hub |
| TRANSFORMERS_CACHE | hf/transformers |
| XDG_CACHE_HOME | xdg |

Offline flags remained1; PYTHONPATH was removed. `GIT_OPTIONAL_LOCKS=0` prevents native Git status from refreshing the protected index. No global environment/configuration was changed.

Writes/mutations outside scratch are rejected, including no-op mkdir attempts. Repository, primary worktree, pinned source/model, adaptation checkpoint, artifact and fixture roots are protected. Rename/link/symlink source and destination are both checked; lexical and resolved path checks prevent scratch aliases escaping to protected/outside locations. Any network attempt, dataset open or adaptation checkpoint open fails closed. The first denial is sticky and checked before/after load and after dependency exit, including exceptions swallowed by dependencies.

The child registers its final result callback before importing dependencies, so their atexit mutations are included in the audit. The parent captures raw bytes, verifies canonical child output, inventories the scratch namespace, then removes exactly that checked namespace. Transport failure tests cover timeout, missing result and abnormal child exit: one invocation, no retry, sanitized blocker, unknown counters where evidence is unavailable, and safe inventory/cleanup attempts.

## Actual audit events and cleanup

| Audit summary | Count |
| --- | --- |
| Total filesystem events | 21 |
| Allowed scratch events | 21 |
| Allowed scratch open-for-write events | 2 |
| Denied protected / outside writes | 0 / 0 |
| Network attempts | 0 |
| Dataset / checkpoint open attempts | 0 / 0 |

| Event type | Count |
| --- | --- |
| open | 2 |
| os.mkdir | 13 |
| os.remove | 3 |
| os.link | 1 |
| os.rmdir | 1 |
| os.utime | 1 |

Every recorded event occurred in stage `laya_load`. The two-ended link has two path details but counts as one event. All details fit within the 200-detail cap. The sequence includes `tmp/lirt6o7b` write/remove, `tmp/tmpc5x6esnt/probe-source` touch/write, link to `probe-link`, removal of both probe files and their directory, plus repeated torchinductor mkdir attempts. No denied operation was recorded.

After dependency exit the scratch **file inventory was empty**; no surviving file needed a size/hash entry. Transient file contents were never committed. `scratch_created=true`, `scratch_cleaned=true`, and the root is absent afterward. No subsequent load followed cleanup.

Python audit hooks record Python filesystem/network events, not every native-library system call. Protected model/source/evidence byte identities provide an additional before/after check; this report does not claim a native OS sandbox.

## Protected identities

All before/after identity dictionaries are exactly equal. Canonical model aggregate was recomputed, not merely copied from prior metadata. No adaptation checkpoint file was opened, hashed or deserialized by any diagnostic mode.

| Identity | Before = after |
| --- | --- |
| Pinned Laya source, clean | 42626c348753fbb17572a813127df2278a1ec527 |
| Model/tokenizer revision | 052592a15d198d9ad47da779604259b10b47b7aa |
| Full model aggregate | eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf |
| Primary weight SHA | 9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204 |
| Tokenizer JSON | 609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f |
| Tokenizer config | 2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f |
| Laya config | 25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6 |
| Qualified venv inventory | 3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337 |

Before load, the tokenizer config explicitly passed the pinned `_fix_tokenizer_config` no-op predicates: tokenizer_class is neither null nor TokenizersBackend; extra_special_tokens is not a list. Its byte hash remained unchanged.

Qualified Python 3.14.7 used `-B -X utf8`; torch 2.13.0+rocm10.0.0, HIP 7.15.26333, transformers 4.57.6, safetensors 0.7.0, huggingface-hub 0.36.2, numpy 2.3.5. No package changes.

| Historical source | Before = after SHA-256 |
| --- | --- |
| `local_ai_stage_b_laya_adapter.py` | `cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e` |
| `local_ai_stage_b_laya_forward_backward_smoke.py` | `80ac4a2ba4587d44e830f45bce31215517e5e3b1387167ca6725964f0a3fdd4e` |
| `local_ai_stage_b_laya_model_load_preflight.py` | `10770d932e3c76b501e44ad77225df962d09ad86af97428649fbc9c55169acd1` |
| `local_ai_stage_b_laya_s3_pr79_validation_diagnostic.py` | `4b259bd9629628aeb3d25ad231521a745cfec81ac0ea6ce6786386259ef94b4f` |
| `local_ai_stage_b_laya_s3_research.py` | `b01a254db9bfb1d84023c0f9d88ff7d49ccb789ff7888961ea7e000dfa2d4388` |
| `local_ai_stage_b_laya_small_adaptation.py` | `85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e` |
| `local_ai_stage_b_laya_span_decoder.py` | `f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845` |
| `local_ai_stage_b_laya_span_representability_audit.py` | `6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087` |
| `local_ai_stage_b_laya_span_seam_design.py` | `7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72` |
| `local_ai_stage_b_laya_span_seam_implementation_verify.py` | `35203544303153cab0df03145bddb21a6c6f08f0d97f5b4f213cedfab115c3e2` |
| `local_ai_stage_b_laya_training_pipeline_smoke.py` | `95c6d818e5b6a0db273bb4f5a1e25486f0cfa152fa7000002e7d82c3f64240e8` |

PR #79 accepted canonical SHA remains `4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8`; PR #86 blocker canonical remains `ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd`. Both JSON/report byte hashes are recorded unchanged in the new JSON. Neither accepted evidence nor historical runners were edited.

## Tests, scope and remaining gate

- Before live: **130 passed, 1 skipped** (durable-result test); after live: **131 passed**, including the durable record. Suites cover this diagnostic, PR #72 load contract and hardware selection using CPU/synthetic inputs.
- Required guard categories, protected sources/destinations, scratch allowance, outside rejection, aliases, network, FileNotFoundError errno/winerror/filename/filename2, traceback sanitizer, paths with spaces, one-load counter and no forbidden call paths are covered. A separate stdlib tempfile subprocess exercises real scratch creation/write/cleanup without model/GPU/data access.
- No broad corpus/fixture or checkpoint regression suites were run in this task. No quality benchmark or model rerun.
- Final source/test syntax compilation passed without writing bytecode; base-to-head `git diff --check` passed, including all new files; **26 Markdown relative links** resolved. Zero app/artifact/fixture diff; zero runner/test diff from the pre-live commit. The three primary-worktree hashes are unchanged. Issues #80/#82 title/body/state/comments/updatedAt match pre-task snapshots.

All six active authority values are false: training_authorized, model_compute_authorized, semantic_memory_enabled, local_ai_fallback_approved, LOCAL_SEMANTIC_MEMORY_ENABLED, LOCAL_AI_FALLBACK_APPROVED. No checkpoint/validation/training, held-out/Stage A, app wiring, semantic memory or fallback promotion.

**Next gate:** independent review of this load/guard evidence. Only a future explicitly authorized task may run the PR #79 checkpoint + S3 validation-only diagnostic with the reviewed scratch policy. That validation did not occur here, and full head-only adaptation remains unauthorized. Issue #68 stays OPEN; Issues #80/#82 unchanged; new PR OPEN/UNMERGED.

**Deviation/limit:** the conservative automated root-cause flag remains false because temporary files did not survive shutdown; observed successful temporary-write activity is reported separately without changing the frozen result. There is no new model-quality result.
