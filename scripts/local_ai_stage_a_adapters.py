"""Benchmark-only adapters for the fixed Local AI Stage A pilots.

The adapters expose only untrusted semantic evidence through the common
benchmark schema.  They do not import ``app`` and never return a
``ValidatedAction``, provider identity, URL, path, or execution target.

The decoder and encoder candidates deliberately report
``slot_evidence_available=False``: their released interfaces answer typed
questions, but do not extract the track/artist/album slots required by this
Agent.  The runner records their top-level intent evidence separately rather
than inventing slot values.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from local_ai_benchmark_harness import (
    AdapterRoute,
    BenchmarkDecision,
    BenchmarkRequest,
)


class StageAAdapterError(RuntimeError):
    """Sanitized adapter failure category used by the benchmark runner."""

    def __init__(self, kind: str, message: str = "") -> None:
        self.kind = kind
        super().__init__(message or kind)


class StageATimeoutError(StageAAdapterError):
    def __init__(self) -> None:
        super().__init__("timeout")


class StageAMalformedOutputError(StageAAdapterError):
    def __init__(self) -> None:
        super().__init__("malformed_output")


class StageABackendError(StageAAdapterError):
    def __init__(self, message: str = "backend_failure") -> None:
        super().__init__("backend_failure", message)


class StageAModelBlockedError(StageAAdapterError):
    """A reviewed candidate cannot be run because its released checkpoint is unavailable."""

    def __init__(self, message: str = "model_blocked") -> None:
        super().__init__("model_blocked", message)


OPTION_INTENT_QUESTION: dict[str, Any] = {
    "type": "choice",
    "instructions": (
        "Classify only the top-level request type. Choose spotify_play_track only when "
        "the state explicitly asks to play or listen to a specifically named song. "
        "Choose unknown for controls, candidate selection, hostile/system text, or "
        "a request without a named song."
    ),
    "criteria": {
        # Both released option-scoring routes receive the same labels.  The
        # short ``play`` label is a single Qwen token; using the production
        # schema name here would make systemone-lite score only its first
        # sub-token under its released _encode_symbol implementation.
        "play": "a request to play or listen to a named song",
        "unknown": "anything else, unsafe, or unsupported",
    },
}


# These identities are intentionally pinned in source before any model
# download.  File sizes are the upstream model.safetensors sizes read from
# the Hugging Face model tree on 2026-09-21.
STAGE_A_IDENTITIES: dict[str, dict[str, Any]] = {
    "qwen2.5-coder-1.5b-instruct": {
        "model_id": "qwen2.5-coder-1.5b-instruct",
        "repository_revision": "local-lmstudio-catalog",
        "model_revision": (
            "alphaduriendur/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF/"
            "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
        ),
        "license": "Apache-2.0 (Qwen base; local GGUF catalog entry)",
        "parameter_count": 1_500_000_000,
        "model_file_bytes": 986_048_576,
        "precision": "q4",
        "quantization": "Q4_K_M",
        "backend": "lmstudio-loopback",
        "hardware_alignment_status": "LMSTUDIO_LOCAL_BACKEND_GPU_OFFLOAD_UNQUALIFIED",
        "quality_run_status": "control loopback quality run completed",
        "route": AdapterRoute.AUTOREGRESSIVE_STRICT_SCHEMA.value,
    },
    "systemone-lite": {
        "model_id": "dwidlee/systemone-lite-0.5b",
        "repository_revision": "0e3373191d3904a070f96d0ed211e6bea8d9ebf6",
        "model_revision": "06b28ed3c5da1d94a6abc015df566ae6408dc5be",
        "license": "Apache-2.0",
        "parameter_count": 494_032_768,
        "model_file_bytes": 988_097_824,
        "precision": "bfloat16 weights; CPU route uses float32",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.DECODER_OPTION_SCORING.value,
    },
    "laya": {
        "model_id": "convaiinnovations/laya-multilingual",
        "repository_revision": "42626c348753fbb17572a813127df2278a1ec527",
        "model_revision": "052592a15d198d9ad47da779604259b10b47b7aa",
        "license": "Apache-2.0",
        "parameter_count": 321_908_998,
        "model_file_bytes": 643_835_514,
        "precision": "float16 weights; CPU route uses float32",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.ENCODER_CLASSIFICATION.value,
    },
    "kev": {
        "model_id": "jaredpalmer/kev-0.5b",
        "repository_revision": "e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c",
        "model_revision": "2679c20e6dde32fb3c4f97ecdad2e6e92bb88a06",
        "base_model": "Qwen/Qwen2.5-0.5B",
        "base_model_revision": "060db6499f32faf8b98477b0a26969ef7d8b9987",
        "license": "Apache-2.0 adapter/head; Apache-2.0 Qwen2.5 base",
        "parameter_count": 494_032_768,
        # The Hub checkpoint contains the adapter/head only; the Qwen base is
        # a separate download and is intentionally called out in the report.
        "model_file_bytes": 37_074_383,
        "precision": "fp32",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.DECODER_OPTION_SCORING.value,
    },
    "eve-rlcd": {
        "model_id": "anthonym21/qwen3-0.6b-rlcd-decision",
        "repository_revision": "57a179b7b1bedc80f65bf42ccda129dd1888272f",
        "model_revision": "b327ec5efb5fdbf8bfafa3b369720ac5f6434b05",
        "base_model": "Qwen/Qwen3-0.6B-Base",
        "base_model_revision": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
        "license": "MIT code; Apache-2.0 Qwen3 weights/base",
        "parameter_count": 596_049_920,
        "model_file_bytes": 2_384_233_112,
        "precision": "fp32",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.DECODER_OPTION_SCORING.value,
    },
    "Verdict-open-jev": {
        "model_id": "heman10x/rlcd-modernbert-151m",
        "repository_revision": "30f15564821626ca5c1ad5b2638c4eb7078787dd",
        "model_revision": "8af2496eb63c7fa66d7d234e1f62629380030eb4",
        "base_model": "knowledgator/gliclass-modern-base-v2.0 / ModernBERT-base",
        "base_model_revision": "9320398ab6ca50946e2edcb9ec89649c0274c978",
        "license": "Apache-2.0 license text; GitHub classifier unasserted; HF card Apache-2.0",
        "parameter_count": 151_378_176,
        "model_file_bytes": 605_529_340,
        "precision": "fp32",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.ENCODER_CLASSIFICATION.value,
    },
    "decider": {
        "model_id": "Mapika/decider-2b",
        "repository_revision": "c4daaac28af9fea95d627015cffa2dd5a5926ee6",
        "model_revision": "b37f7e1ba3fbc9238004cf531fabbee2619973fd",
        "base_model": "Qwen/Qwen3.5-2B-Base",
        # The model card does not declare a resolved base snapshot.  Keep the
        # fact explicit rather than manufacturing a base revision.
        "base_model_revision": "not declared by the model card",
        "license": "Apache-2.0",
        "parameter_count": 1_881_825_088,
        "model_file_bytes": 3_763_692_048,
        "precision": "bfloat16 checkpoint; CPU route uses float32",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.DECODER_OPTION_SCORING.value,
    },
    "system-one-open": {
        "model_id": "mithalouni/system-one-open",
        "repository_revision": "77f1f7cccf8aa752e0ed7edcc8d2094bac707bdc",
        "model_revision": "released trained checkpoint unavailable",
        "base_model": "unsloth/gemma-3-270m-it (recipe reference only)",
        "base_model_revision": "not applicable; no released trained checkpoint",
        "license": "MIT",
        "parameter_count": 270_000_000,
        "model_file_bytes": None,
        "precision": "not run",
        "quantization": "not run",
        "backend": "not-run-model-blocked",
        "hardware_alignment_status": "MODEL_BLOCKED",
        "quality_run_status": "MODEL_BLOCKED: released trained checkpoint unavailable",
        "route": AdapterRoute.DECODER_OPTION_SCORING.value,
    },
    "open-jev-deberta-v3-large": {
        "model_id": "com-kotobalabs/open-jev-deberta-v3-large",
        "repository_revision": "bundled typed_decisions source at model revision",
        "model_revision": "19bf9a64815add579fbf6c907bef584d9277a8e4",
        "base_model": "microsoft/deberta-v3-large",
        "base_model_revision": "64a8c8eab3e352a784c658aef62be1662607476f",
        "license": "Apache-2.0 checkpoint; MIT base model",
        "parameter_count": 437_159_937,
        "model_file_bytes": 1_736_094_384,
        "precision": "fp32 route on CPU",
        "quantization": "none",
        "backend": "python-cpu-fallback-until-amd-backend-proven",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_BLOCKED",
        "quality_run_status": "exploratory CPU quality run completed",
        "route": AdapterRoute.ENCODER_CLASSIFICATION.value,
    },
}


def _prepend_path(path: Path, *relative_candidates: str) -> None:
    """Add a pinned upstream source directory without changing the app path."""

    root = path.resolve()
    for relative in relative_candidates:
        candidate = root / relative
        if candidate.is_dir():
            value = str(candidate)
            if value not in sys.path:
                sys.path.insert(0, value)
            return
    raise StageABackendError("pinned upstream source directory not found")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dumped
    if isinstance(value, Mapping):
        return value
    raise StageAMalformedOutputError()


@contextmanager
def _systemone_tokenizer_compatibility(model_path: Path):
    """Bridge one released tokenizer metadata shape, then restore it.

    The checkpoint currently stores ``extra_special_tokens`` as a JSON list,
    while the installed Transformers tokenizer expects a mapping.  The
    upstream Laya loader has an equivalent compatibility shim.  Keep this
    change local to the benchmark loader and never persist a modified model
    artifact.
    """

    config_path = model_path / "tokenizer_config.json"
    original = config_path.read_text(encoding="utf-8")
    changed = False
    try:
        payload = json.loads(original)
        extra = payload.get("extra_special_tokens") if isinstance(payload, Mapping) else None
        if isinstance(extra, list):
            payload["extra_special_tokens"] = {
                f"extra_{index}": token for index, token in enumerate(extra)
            }
            config_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed = True
        yield changed
    finally:
        if changed:
            config_path.write_text(original, encoding="utf-8")


def _typed_choice_decision(answer: Any) -> BenchmarkDecision:
    payload = _as_mapping(answer)
    choice = payload.get("choice")
    intent_by_label = {"play": "spotify_play_track", "unknown": "unknown"}
    if choice not in intent_by_label:
        raise StageAMalformedOutputError()
    probabilities = payload.get("probabilities", {})
    if not isinstance(probabilities, Mapping):
        raise StageAMalformedOutputError()
    option_scores: dict[str, float] = {}
    for option in ("play", "unknown"):
        score = probabilities.get(option)
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise StageAMalformedOutputError()
        option_scores[option] = float(score)
    confidence = payload.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool) or not isinstance(confidence, (int, float))
    ):
        raise StageAMalformedOutputError()
    return BenchmarkDecision(
        intent=intent_by_label[str(choice)],
        confidence=float(confidence) if confidence is not None else None,
        option_scores={
            "spotify_play_track": option_scores["play"],
            "unknown": option_scores["unknown"],
        },
        slot_evidence_available=False,
    )


class ControlLMStudioAdapter:
    """Use the existing strict-schema LM Studio control route."""

    route = AdapterRoute.AUTOREGRESSIVE_STRICT_SCHEMA

    def __init__(self, base_url: str, model_name: str, timeout_seconds: float) -> None:
        self.model_name = model_name
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client: Any | None = None

    def prepare(self) -> None:
        try:
            from ai_model_poc import LMStudioClient, require_dependencies

            require_dependencies()
            self._client = LMStudioClient(self._base_url, self._timeout_seconds)
        except StageAAdapterError:
            raise
        except Exception as exc:  # do not expose raw dependency details in result artifacts
            raise StageABackendError("control dependency or endpoint setup failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._client is None:
            self.prepare()
        try:
            from ai_model_poc import (
                AIIntentResult,
                build_messages,
                finalize_semantics,
                parse_json_content,
            )

            content = self._client.complete(
                self.model_name,
                build_messages({"input": request.text}),
                structured=True,
            )
            payload, error = parse_json_content(content)
            if error is not None or payload is None:
                raise StageAMalformedOutputError()
            parsed = AIIntentResult.model_validate(payload)
            final, _grounding_ok, _reason = finalize_semantics(
                {"input": request.text}, parsed
            )
            return BenchmarkDecision.from_mapping(final)
        except StageAAdapterError:
            raise
        except TimeoutError as exc:
            raise StageATimeoutError() from exc
        except RuntimeError as exc:
            # LM Studio's client deliberately exposes only category-level errors
            # to this benchmark boundary.
            if str(exc).startswith("request timed out"):
                raise StageATimeoutError() from exc
            raise StageABackendError() from exc
        except Exception as exc:
            raise StageAMalformedOutputError() from exc


class SystemOneLiteAdapter:
    """Run the released SystemOne option-scoring path as a typed classifier."""

    route = AdapterRoute.DECODER_OPTION_SCORING

    def __init__(self, source_root: Path, model_path: Path) -> None:
        self.model_name = "dwidlee/systemone-lite-0.5b"
        self._source_root = source_root
        self._model_path = model_path
        self._engine: Any | None = None

    def prepare(self) -> None:
        if self._engine is not None:
            return
        try:
            _prepend_path(self._source_root, "src", ".")
            from systemone_lite import infer

            with _systemone_tokenizer_compatibility(self._model_path):
                loaded = infer.load_model(str(self._model_path))
            self._engine = infer.SystemOneEngine(loaded, use_prefix_cache=True)
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("systemone model load failed") from exc
        except Exception as exc:
            raise StageABackendError("systemone model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._engine is None:
            self.prepare()
        try:
            from systemone_lite.schema import SystemOneRequest

            typed_request = SystemOneRequest(
                state=request.text,
                questions={"intent": OPTION_INTENT_QUESTION},
            )
            response = self._engine.decide(typed_request)
            return _typed_choice_decision(response.answers["intent"])
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("systemone inference failed") from exc


class LayaMultilingualAdapter:
    """Run the released multilingual Laya decision-head path as-is."""

    route = AdapterRoute.ENCODER_CLASSIFICATION

    def __init__(self, source_root: Path, model_path: Path) -> None:
        self.model_name = "convaiinnovations/laya-multilingual"
        self._source_root = source_root
        self._model_path = model_path
        self._agent: Any | None = None

    def prepare(self) -> None:
        if self._agent is not None:
            return
        try:
            _prepend_path(self._source_root, ".")
            import laya

            self._agent = laya.load(str(self._model_path), device="cpu")
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("laya model load failed") from exc
        except Exception as exc:
            raise StageABackendError("laya model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._agent is None:
            self.prepare()
        try:
            result = self._agent.system_one(
                request.text,
                {"intent": OPTION_INTENT_QUESTION},
            )
            answers = result.get("answers") if isinstance(result, Mapping) else None
            if not isinstance(answers, Mapping) or "intent" not in answers:
                raise StageAMalformedOutputError()
            return _typed_choice_decision(answers["intent"])
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("laya inference failed") from exc


class KevAdapter:
    """Run the pinned original Kev-0.5B pointer-head checkpoint."""

    route = AdapterRoute.DECODER_OPTION_SCORING

    def __init__(self, source_root: Path, model_path: Path, base_path: Path) -> None:
        self.model_name = "jaredpalmer/kev-0.5b"
        self._source_root = source_root
        self._model_path = model_path
        self._base_path = base_path
        self._tokenizer: Any | None = None
        self._model: Any | None = None

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            _prepend_path(self._source_root, ".")
            # Import the released model implementation directly.  The
            # upstream evaluate module imports its optional dataset package at
            # module import time, even though the inference loader does not
            # need datasets; the direct path keeps this benchmark dependency
            # narrow while retaining the released model/mask implementation.
            from kev.model import DecisionModel, load_tokenizer
            from peft import PeftModel
            import torch

            head = torch.load(
                self._model_path / "head.pt", map_location="cpu", weights_only=False
            )
            self._tokenizer = load_tokenizer(str(self._base_path))
            self._model = DecisionModel(
                str(self._base_path),
                self._tokenizer,
                "cpu",
                lora=None,
                revision=None,
                head_dim=int(head.get("head_dim", 256)),
                option_isolation=bool(head.get("option_isolation", False)),
                dtype=torch.float32,
            )
            self._model.lm = PeftModel.from_pretrained(
                self._model.lm, str(self._model_path)
            ).to("cpu")
            self._model.lm = self._model.lm.merge_and_unload()
            self._model.head.load_state_dict(head["head"])
            self._model.eval()
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("kev model load failed") from exc
        except Exception as exc:
            raise StageABackendError("kev model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._model is None:
            self.prepare()
        try:
            record = {
                "state": request.text,
                "questions": [
                    {
                        "instr": OPTION_INTENT_QUESTION["instructions"],
                        "options": list(OPTION_INTENT_QUESTION["criteria"]),
                        "label": 0,
                    }
                ],
            }
            encoded = self._model.encode(self._tokenizer, record, strict=True)
            probabilities = self._model.probs(encoded)[0].tolist()
            answer = "play" if probabilities[0] >= probabilities[1] else "unknown"
            return _typed_choice_decision(
                {
                    "choice": answer,
                    "confidence": max(probabilities[0], probabilities[1]),
                    "probabilities": {
                        "play": probabilities[0],
                        "unknown": probabilities[1],
                    },
                }
            )
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("kev inference failed") from exc


class EveRLCDAdapter:
    """Run the pinned Eve RLCD decision-only export as a typed classifier."""

    route = AdapterRoute.DECODER_OPTION_SCORING

    def __init__(self, source_root: Path, model_path: Path) -> None:
        self.model_name = "anthonym21/qwen3-0.6b-rlcd-decision"
        self._source_root = source_root
        self._model_path = model_path
        self._decider: Any | None = None

    def prepare(self) -> None:
        if self._decider is not None:
            return
        try:
            _prepend_path(self._source_root, ".")
            from rlcd.decide import Decider

            self._decider = Decider.load(str(self._model_path), device="cpu", fast=False)
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("eve-rlcd model load failed") from exc
        except Exception as exc:
            raise StageABackendError("eve-rlcd model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._decider is None:
            self.prepare()
        try:
            from rlcd.decide import ChoiceQ

            answer = self._decider.ask(
                request.text,
                [
                    ChoiceQ(
                        question=OPTION_INTENT_QUESTION["instructions"],
                        options=list(OPTION_INTENT_QUESTION["criteria"]),
                    )
                ],
                batch_size=1,
                fast=False,
            )[0]
            probabilities = answer.get("probs") if isinstance(answer, Mapping) else None
            value = answer.get("value") if isinstance(answer, Mapping) else None
            if not isinstance(probabilities, Mapping) or value not in {"play", "unknown"}:
                raise StageAMalformedOutputError()
            return _typed_choice_decision(
                {
                    "choice": value,
                    "confidence": answer.get("confidence"),
                    "probabilities": {
                        "play": probabilities.get("play"),
                        "unknown": probabilities.get("unknown"),
                    },
                }
            )
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("eve-rlcd inference failed") from exc


class VerdictOpenJevAdapter:
    """Run Verdict's released ModernBERT/GLiClass choice path."""

    route = AdapterRoute.ENCODER_CLASSIFICATION

    def __init__(self, source_root: Path, model_path: Path) -> None:
        self.model_name = "heman10x/rlcd-modernbert-151m"
        self._source_root = source_root
        self._model_path = model_path
        self._engine: Any | None = None

    def prepare(self) -> None:
        if self._engine is not None:
            return
        try:
            _prepend_path(self._source_root, ".")
            from core.engine_encoder import DecisionEngine

            self._engine = DecisionEngine(model_name_or_path=str(self._model_path), device="cpu")
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("Verdict model load failed") from exc
        except Exception as exc:
            raise StageABackendError("Verdict model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._engine is None:
            self.prepare()
        try:
            from core.primitives import Choice, Option

            query = Choice(
                id="intent",
                question=OPTION_INTENT_QUESTION["instructions"],
                options=(
                    Option(
                        id="play",
                        description=OPTION_INTENT_QUESTION["criteria"]["play"],
                    ),
                    Option(
                        id="unknown",
                        description=OPTION_INTENT_QUESTION["criteria"]["unknown"],
                    ),
                ),
            )
            result = self._engine.evaluate(request.text, [query]).results[0]
            raw = result.probabilities
            play = float(raw.get("play", 0.0))
            unknown = float(raw.get("unknown", 0.0)) + float(
                raw.get("__insufficient_evidence__", 0.0)
            )
            total = play + unknown
            if total <= 0.0:
                raise StageAMalformedOutputError()
            probabilities = {"play": play / total, "unknown": unknown / total}
            choice = "play" if result.selected_id == "play" else "unknown"
            return _typed_choice_decision(
                {
                    "choice": choice,
                    "confidence": probabilities[choice],
                    "probabilities": probabilities,
                }
            )
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("Verdict inference failed") from exc


class DeciderAdapter:
    """Run Mapika's released one-pass typed-decision route on CPU."""

    route = AdapterRoute.DECODER_OPTION_SCORING

    def __init__(self, source_root: Path, model_path: Path) -> None:
        self.model_name = "Mapika/decider-2b"
        self._source_root = source_root
        self._model_path = model_path
        self._decider: Any | None = None

    def prepare(self) -> None:
        if self._decider is not None:
            return
        try:
            _prepend_path(self._source_root, ".")
            import torch
            from decider.infer import Decider

            # The published default temperature is 1.0.  The reviewed
            # Batch-2B protocol fixes this candidate at 1.3 for the CPU
            # quality run, while retaining the released scoring route.
            self._decider = Decider(
                str(self._model_path),
                device="cpu",
                dtype=torch.float32,
                temperature=1.3,
                use_graphs=False,
            )
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("decider model load failed") from exc
        except Exception as exc:
            raise StageABackendError("decider model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._decider is None:
            self.prepare()
        try:
            answer = self._decider.decide(
                request.text,
                [
                    {
                        "question": OPTION_INTENT_QUESTION["instructions"],
                        "options": list(OPTION_INTENT_QUESTION["criteria"]),
                    }
                ],
            )[0]
            if not isinstance(answer, Mapping):
                raise StageAMalformedOutputError()
            return _typed_choice_decision(
                {
                    "choice": answer.get("choice"),
                    "confidence": answer.get("confidence"),
                    "probabilities": answer.get("probs"),
                }
            )
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("decider inference failed") from exc


class OpenJevDebertaAdapter:
    """Run the bundled open-jev DeBERTa typed option-scoring route."""

    route = AdapterRoute.ENCODER_CLASSIFICATION

    def __init__(self, model_path: Path) -> None:
        self.model_name = "com-kotobalabs/open-jev-deberta-v3-large"
        self._model_path = model_path
        self._model: Any | None = None

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            # The pinned model bundle includes the released typed_decisions
            # package.  Import it from that bundle only; no production package
            # or network-backed model lookup is involved.
            _prepend_path(self._model_path, ".")
            from typed_decisions.open_jev import OpenJev

            self._model = OpenJev.from_pretrained(str(self._model_path), device="cpu")
        except StageAAdapterError:
            raise
        except (TimeoutError, MemoryError) as exc:
            raise StageABackendError("open-jev DeBERTa model load failed") from exc
        except Exception as exc:
            raise StageABackendError("open-jev DeBERTa model load or backend failed") from exc

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        if self._model is None:
            self.prepare()
        try:
            answer = self._model.decide(
                request.text,
                [
                    {
                        "type": "choice",
                        "instructions": OPTION_INTENT_QUESTION["instructions"],
                        "options": list(OPTION_INTENT_QUESTION["criteria"]),
                    }
                ],
            )[0]
            if not isinstance(answer, Mapping):
                raise StageAMalformedOutputError()
            return _typed_choice_decision(
                {
                    "choice": answer.get("choice"),
                    "confidence": answer.get("confidence"),
                    "probabilities": answer.get("probabilities"),
                }
            )
        except StageAAdapterError:
            raise
        except Exception as exc:
            raise StageABackendError("open-jev DeBERTa inference failed") from exc


class SystemOneOpenBlockedAdapter:
    """Represent the reviewed checkpoint blocker without running a substitute."""

    route = AdapterRoute.DECODER_OPTION_SCORING
    model_name = "mithalouni/system-one-open"

    def prepare(self) -> None:
        raise StageAModelBlockedError(
            "system-one-open released trained checkpoint is unavailable; no base substitution allowed"
        )

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        del request
        raise StageAModelBlockedError(
            "system-one-open released trained checkpoint is unavailable; no base substitution allowed"
        )


def identity_for(candidate_name: str) -> dict[str, Any]:
    try:
        return dict(STAGE_A_IDENTITIES[candidate_name])
    except KeyError as exc:
        raise ValueError(f"unsupported Stage A pilot candidate: {candidate_name}") from exc
