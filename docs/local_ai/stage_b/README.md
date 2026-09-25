# Local AI — Stage B

## Current State (2026-09-25)

- RX 9070 XT / gfx1201 hardware preflight: **PASSED**
- Laya ROCm dependency bootstrap: **PASSED**
- Pinned Laya artifact/source identity: **VERIFIED**
- First Laya model-load gate: **BLOCKED** (before device residency)
- Root cause: PyTorch `torch/_inductor/utils.py::load_template()` reading `.jinja` template without explicit UTF-8 encoding under Windows code page 950 (cp950)
- Classification: `OTHER_DEPENDENCY_CP950`
- Fix: not yet validated
- Authority flags: all four remain `false`
- See [GitHub Issue #68](https://github.com/QWQOUOT485/siri/issues/68) for detailed blocker history

## Plan Documents

| Document | Description |
|----------|-------------|
| [Adaptation Plan](LOCAL_AI_STAGE_B_ADAPTATION_PLAN.md) | Stage B design and training plan |
| [Corpus Build Protocol](LOCAL_AI_STAGE_B_CORPUS_BUILD_PROTOCOL.md) | Corpus generation and validation protocol |
| [Independent Review Guide](LOCAL_AI_STAGE_B_INDEPENDENT_REVIEW_GUIDE.md) | Review workflow for v6 candidates |

## Evidence

| Document | Date |
|----------|------|
| [RX 9070 XT Hardware Preflight](evidence/LOCAL_AI_STAGE_B_RX9070XT_HARDWARE_PREFLIGHT_2026-09-24.md) | 2026-09-24 |
| [V6 Candidate Evidence](evidence/LOCAL_AI_STAGE_B_V6_CANDIDATE_EVIDENCE.md) | Current |
| [V5 Candidate Evidence](evidence/LOCAL_AI_STAGE_B_V5_CANDIDATE_EVIDENCE.md) | Historical (superseded by v6) |
