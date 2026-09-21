"""Fixed, documentation-aligned candidate manifest for the benchmark only.

This module contains identity and intent metadata only.  It never resolves,
downloads, loads, or executes a model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    """One candidate row from the reviewed benchmark plan."""

    candidate_name: str
    backbone: str
    inference_route: str
    upstream_reference: str
    stage_a_status: str = "not_run"
    expected_backend_compatibility: str = "unverified; check on RX 9070 XT during preflight"
    model_id: str | None = None
    repository_revision: str | None = None
    model_revision: str | None = None
    base_model: str | None = None
    base_model_revision: str | None = None
    license: str | None = None
    parameter_count: int | None = None
    model_file_bytes: int | None = None

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


CONTROL_BASELINE = CandidateSpec(
    candidate_name="qwen2.5-coder-1.5b-instruct",
    backbone="Qwen2.5-Coder 1.5B Instruct",
    inference_route="autoregressive strict-schema JSON",
    upstream_reference="existing local AI control configuration",
    expected_backend_compatibility="existing control path; exact backend must be recorded before comparison",
    model_id="qwen2.5-coder-1.5b-instruct",
    repository_revision="local-lmstudio-catalog",
    model_revision=(
        "alphaduriendur/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF/"
        "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    ),
    license="Apache-2.0 (Qwen base; local GGUF catalog entry)",
    parameter_count=1_500_000_000,
    model_file_bytes=986_048_576,
)


FIXED_CANDIDATES: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        candidate_name="systemone-lite",
        backbone="Qwen2.5-0.5B-Instruct",
        inference_route="frozen/SFT option-restricted next-token scoring + prefix KV",
        upstream_reference="https://github.com/fritzprix/systemone-lite",
        expected_backend_compatibility="published RTX 3060 path; RX 9070 XT compatibility unverified",
        model_id="dwidlee/systemone-lite-0.5b",
        repository_revision="0e3373191d3904a070f96d0ed211e6bea8d9ebf6",
        model_revision="06b28ed3c5da1d94a6abc015df566ae6408dc5be",
        license="Apache-2.0",
        parameter_count=494_032_768,
        model_file_bytes=988_097_824,
    ),
    CandidateSpec(
        candidate_name="kev",
        backbone="Qwen2.5-0.5B",
        inference_route="LoRA + trained pointer/readout decision head",
        upstream_reference="https://github.com/jaredpalmer/kev",
        expected_backend_compatibility="published CUDA/MPS path; RX 9070 XT compatibility unverified",
        model_id="jaredpalmer/kev-0.5b",
        repository_revision="e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c",
        model_revision="2679c20e6dde32fb3c4f97ecdad2e6e92bb88a06",
        base_model="Qwen/Qwen2.5-0.5B",
        base_model_revision="060db6499f32faf8b98477b0a26969ef7d8b9987",
        license="Apache-2.0 adapter/head; Apache-2.0 Qwen2.5 base",
        parameter_count=494_032_768,
        model_file_bytes=37_074_383,
    ),
    CandidateSpec(
        candidate_name="eve-rlcd",
        backbone="Qwen3-0.6B-Base",
        inference_route="supervised warmup + RLCD-style calibrated decision training",
        upstream_reference="https://github.com/anthony-maio/eve-rlcd",
        expected_backend_compatibility="published CUDA path; RX 9070 XT compatibility blocked in current venv",
        model_id="anthonym21/qwen3-0.6b-rlcd-decision",
        repository_revision="57a179b7b1bedc80f65bf42ccda129dd1888272f",
        model_revision="b327ec5efb5fdbf8bfafa3b369720ac5f6434b05",
        base_model="Qwen/Qwen3-0.6B-Base",
        base_model_revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
        license="MIT code; Apache-2.0 Qwen3 weights/base",
        parameter_count=596_049_920,
        model_file_bytes=2_384_233_112,
    ),
    CandidateSpec(
        candidate_name="decider",
        backbone="Qwen3.5-2B-Base",
        inference_route="one-pass typed decisions with trained label projection",
        upstream_reference="https://github.com/Mapika/decider",
        expected_backend_compatibility="RX 9070 XT backend blocked in current venv; CPU exploratory route",
        model_id="Mapika/decider-2b",
        repository_revision="c4daaac28af9fea95d627015cffa2dd5a5926ee6",
        model_revision="b37f7e1ba3fbc9238004cf531fabbee2619973fd",
        base_model="Qwen/Qwen3.5-2B-Base",
        base_model_revision="not declared by the model card",
        license="Apache-2.0",
        parameter_count=1_881_825_088,
        model_file_bytes=3_763_692_048,
    ),
    CandidateSpec(
        candidate_name="system-one-open",
        backbone="Gemma 3 270M first; Gemma 4 E2B only if hardware fit is proven",
        inference_route="trained Gemma Jev-style model",
        upstream_reference="https://github.com/mithalouni/system-one-open",
        expected_backend_compatibility="blocked: released trained checkpoint unavailable; no base substitution",
        model_id="mithalouni/system-one-open",
        repository_revision="77f1f7cccf8aa752e0ed7edcc8d2094bac707bdc",
        model_revision="released trained checkpoint unavailable",
        base_model="unsloth/gemma-3-270m-it (recipe reference only)",
        base_model_revision="not applicable; no released trained checkpoint",
        license="MIT",
        parameter_count=270_000_000,
    ),
    CandidateSpec(
        candidate_name="laya",
        backbone="prefer multilingual mmBERT checkpoint (~322M class)",
        inference_route="non-autoregressive multilingual encoder + decision head",
        upstream_reference="https://github.com/NandhaKishorM/laya",
        expected_backend_compatibility="AMD encoder backend compatibility unverified",
        model_id="convaiinnovations/laya-multilingual",
        repository_revision="42626c348753fbb17572a813127df2278a1ec527",
        model_revision="052592a15d198d9ad47da779604259b10b47b7aa",
        license="Apache-2.0",
        parameter_count=321_908_998,
        model_file_bytes=643_835_514,
    ),
    CandidateSpec(
        candidate_name="Verdict-open-jev",
        backbone="ModernBERT ~151M",
        inference_route="very small non-autoregressive encoder decision engine",
        upstream_reference="https://github.com/Heman10x-NGU/Verdict-open-jev",
        expected_backend_compatibility="documented CPU ONNX path; RX 9070 XT path unverified",
        model_id="heman10x/rlcd-modernbert-151m",
        repository_revision="30f15564821626ca5c1ad5b2638c4eb7078787dd",
        model_revision="8af2496eb63c7fa66d7d234e1f62629380030eb4",
        base_model="knowledgator/gliclass-modern-base-v2.0 / ModernBERT-base",
        base_model_revision="9320398ab6ca50946e2edcb9ec89649c0274c978",
        license="Apache-2.0 license text; GitHub classifier unasserted; HF card Apache-2.0",
        parameter_count=151_378_176,
        model_file_bytes=605_529_340,
    ),
    CandidateSpec(
        candidate_name="open-jev-deberta-v3-large",
        backbone="DeBERTa-v3-large",
        inference_route="encoder + typed option scoring + calibrated probabilities",
        upstream_reference="https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large",
        expected_backend_compatibility="RX 9070 XT backend blocked in current venv; CPU exploratory route",
        model_id="com-kotobalabs/open-jev-deberta-v3-large",
        repository_revision="bundled typed_decisions source at model revision",
        model_revision="19bf9a64815add579fbf6c907bef584d9277a8e4",
        base_model="microsoft/deberta-v3-large",
        base_model_revision="64a8c8eab3e352a784c658aef62be1662607476f",
        license="Apache-2.0 checkpoint; MIT base model",
        parameter_count=437_159_937,
        model_file_bytes=1_736_094_384,
    ),
)


OPTIONAL_LITJEV = CandidateSpec(
    candidate_name="LitJev",
    backbone="existing Qwen checkpoint methodology reference",
    inference_route="logits-only inference",
    upstream_reference="https://github.com/zhengxuyu/litjev",
    expected_backend_compatibility="optional methodology; use the existing Qwen control backbone",
)


def candidate_manifest(*, include_optional: bool = False) -> tuple[CandidateSpec, ...]:
    """Return the fixed eight candidates, optionally followed by LitJev."""

    if include_optional:
        return (*FIXED_CANDIDATES, OPTIONAL_LITJEV)
    return FIXED_CANDIDATES


def manifest_as_dicts(*, include_optional: bool = False) -> list[dict[str, Any]]:
    return [candidate.to_dict() for candidate in candidate_manifest(include_optional=include_optional)]


def validate_fixed_candidate_set(candidates: tuple[CandidateSpec, ...] | list[CandidateSpec]) -> None:
    """Reject accidental candidate substitution or duplication."""

    expected = tuple(candidate.candidate_name for candidate in FIXED_CANDIDATES)
    actual = tuple(candidate.candidate_name for candidate in candidates)
    if actual != expected:
        raise ValueError(f"fixed benchmark candidate set changed: expected {expected!r}, found {actual!r}")
