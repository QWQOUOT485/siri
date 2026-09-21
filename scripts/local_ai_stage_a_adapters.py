"""Benchmark-only adapters for the three-model Local AI Stage A pilot.

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


def identity_for(candidate_name: str) -> dict[str, Any]:
    try:
        return dict(STAGE_A_IDENTITIES[candidate_name])
    except KeyError as exc:
        raise ValueError(f"unsupported Stage A pilot candidate: {candidate_name}") from exc
