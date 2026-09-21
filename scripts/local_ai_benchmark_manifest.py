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
        expected_backend_compatibility="AMD backend compatibility unverified",
    ),
    CandidateSpec(
        candidate_name="eve-rlcd",
        backbone="Qwen3-0.6B-Base",
        inference_route="supervised warmup + RLCD-style calibrated decision training",
        upstream_reference="https://github.com/anthony-maio/eve-rlcd",
        expected_backend_compatibility="AMD backend compatibility unverified",
    ),
    CandidateSpec(
        candidate_name="decider",
        backbone="Qwen3.5-2B-Base",
        inference_route="one-pass typed decisions with trained label projection",
        upstream_reference="https://github.com/Mapika/decider",
        expected_backend_compatibility="AMD backend compatibility unverified; record VRAM fit",
    ),
    CandidateSpec(
        candidate_name="system-one-open",
        backbone="Gemma 3 270M first; Gemma 4 E2B only if hardware fit is proven",
        inference_route="trained Gemma Jev-style model",
        upstream_reference="https://github.com/mithalouni/system-one-open",
        expected_backend_compatibility="AMD backend compatibility unverified; record checkpoint fit",
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
        expected_backend_compatibility="AMD encoder backend compatibility unverified",
    ),
    CandidateSpec(
        candidate_name="open-jev-deberta-v3-large",
        backbone="DeBERTa-v3-large",
        inference_route="encoder + typed option scoring + calibrated probabilities",
        upstream_reference="https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large",
        expected_backend_compatibility="AMD encoder backend compatibility unverified; record VRAM fit",
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
