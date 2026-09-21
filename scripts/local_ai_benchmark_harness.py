"""Benchmark-only corpus, result-schema, adapter, and metric infrastructure.

This module intentionally has no imports from ``app`` and no path from model
output to a production action.  It records evidence for later review; it is
not a Local AI execution path.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from statistics import median
from typing import Any, Callable, Mapping, Protocol, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_PATH = REPO_ROOT / "tests" / "fixtures" / "ai_intent_cases.json"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "runtime" / "ai_poc"
EXPECTED_CORPUS_CASE_COUNT = 109
FROZEN_CORPUS_SHA256 = "60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55"

ALLOWED_INTENTS = frozenset({"spotify_play_track", "unknown"})
ALLOWED_AI_SCOPES = frozenset({"supported", "deterministic_only", "safety_only"})
ALLOWED_LANGUAGE_SLICES = frozenset({"chinese", "english", "mixed"})
FORBIDDEN_RESULT_KEYS = frozenset(
    {
        "action",
        "app_path",
        "clarification_token",
        "confirmation_token",
        "executable_path",
        "filesystem_path",
        "powershell",
        "shell",
        "shutdown",
        "spotify_uri",
        "track_id",
        "url",
        "validated_action",
    }
)


class BenchmarkSchemaError(ValueError):
    """Raised when benchmark-only data violates the closed schema."""


class CorpusDriftError(ValueError):
    """Raised when the reviewed frozen corpus no longer matches its identity."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkSchemaError(f"{name} must be a non-empty string")
    return value.strip()


def _require_rate(name: str, value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkSchemaError(f"{name} must be a number or null")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise BenchmarkSchemaError(f"{name} must be between 0 and 1")
    return number


def _require_nonnegative(name: str, value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkSchemaError(f"{name} must be a non-negative number or null")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise BenchmarkSchemaError(f"{name} must be a finite non-negative number")
    return number


def _require_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise BenchmarkSchemaError(f"{name} must be boolean")
    return value


def _require_count(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BenchmarkSchemaError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class CorpusIdentity:
    relative_path: str
    case_count: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FrozenCorpus:
    identity: CorpusIdentity
    cases: tuple[Mapping[str, Any], ...]


def _load_corpus_payload(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusDriftError(f"cannot read frozen corpus: {path}") from exc
    if not isinstance(payload, list) or any(not isinstance(case, dict) for case in payload):
        raise CorpusDriftError("frozen corpus must be a JSON array of objects")
    ids: set[str] = set()
    for case in payload:
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise CorpusDriftError("frozen corpus case IDs must be non-empty and unique")
        if not isinstance(case.get("category"), str) or not isinstance(case.get("input"), str):
            raise CorpusDriftError(f"frozen corpus case {case_id!r} is missing category/input")
        if not isinstance(case.get("expected"), dict):
            raise CorpusDriftError(f"frozen corpus case {case_id!r} is missing expected result")
        ids.add(case_id)
    return payload


def compute_corpus_identity(path: Path = DEFAULT_CORPUS_PATH) -> CorpusIdentity:
    """Compute the stable content identity without changing the fixture."""

    payload = _load_corpus_payload(path)
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    try:
        relative_path = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        relative_path = str(path.resolve())
    return CorpusIdentity(relative_path, len(payload), digest)


def load_frozen_corpus(
    path: Path = DEFAULT_CORPUS_PATH,
    *,
    expected_case_count: int | None = EXPECTED_CORPUS_CASE_COUNT,
    expected_sha256: str | None = FROZEN_CORPUS_SHA256,
) -> FrozenCorpus:
    """Load and verify the reviewed 109-case corpus, detecting content drift."""

    payload = _load_corpus_payload(path)
    identity = compute_corpus_identity(path)
    if expected_case_count is not None and identity.case_count != expected_case_count:
        raise CorpusDriftError(
            f"frozen corpus case count changed: expected {expected_case_count}, found {identity.case_count}"
        )
    if expected_sha256 is not None and identity.sha256 != expected_sha256:
        raise CorpusDriftError(
            f"frozen corpus hash changed: expected {expected_sha256}, found {identity.sha256}"
        )
    return FrozenCorpus(identity, tuple(payload))


class AdapterRoute(str, Enum):
    AUTOREGRESSIVE_STRICT_SCHEMA = "autoregressive_strict_schema"
    DECODER_OPTION_SCORING = "decoder_option_scoring"
    ENCODER_CLASSIFICATION = "encoder_classification"


@dataclass(frozen=True, slots=True)
class BenchmarkRequest:
    """Untrusted text sent to a benchmark adapter; no trusted entities."""

    case_id: str
    text: str
    options: tuple[str, ...] = ("spotify_play_track", "unknown")

    def __post_init__(self) -> None:
        _require_text("case_id", self.case_id)
        _require_text("text", self.text)
        if self.options != ("spotify_play_track", "unknown"):
            raise BenchmarkSchemaError("benchmark options must remain the closed intent set")


@dataclass(frozen=True, slots=True)
class BenchmarkDecision:
    """Closed, untrusted semantic evidence; never a production action."""

    intent: str
    track: str | None = None
    artist: str | None = None
    album: str | None = None
    confidence: float | None = None
    option_scores: Mapping[str, float] = field(default_factory=dict)
    # Typed decision models may intentionally expose only the top-level
    # option.  Keep that limitation explicit instead of letting a runner
    # mistake a missing track/artist/album extraction for a correct result.
    slot_evidence_available: bool = True

    def __post_init__(self) -> None:
        if self.intent not in ALLOWED_INTENTS:
            raise BenchmarkSchemaError("intent is outside the benchmark allowlist")
        for field_name in ("track", "artist", "album"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(field_name, value)
                if len(value) > 300 or any(ord(char) < 32 or ord(char) == 127 for char in value):
                    raise BenchmarkSchemaError(f"{field_name} is out of bounds")
        if self.intent == "spotify_play_track" and self.track is None and self.slot_evidence_available:
            raise BenchmarkSchemaError("spotify_play_track requires a track")
        if self.intent == "unknown" and any(value is not None for value in (self.track, self.artist, self.album)):
            raise BenchmarkSchemaError("unknown cannot carry semantic slots")
        _require_rate("confidence", self.confidence)
        if not isinstance(self.option_scores, Mapping):
            raise BenchmarkSchemaError("option_scores must be a mapping")
        for option, score in self.option_scores.items():
            if option not in ALLOWED_INTENTS:
                raise BenchmarkSchemaError("option_scores contains an unapproved option")
            _require_rate(f"option_scores[{option}]", score)
        _require_bool("slot_evidence_available", self.slot_evidence_available)
        if not self.slot_evidence_available and any(
            value is not None for value in (self.track, self.artist, self.album)
        ):
            raise BenchmarkSchemaError(
                "slot evidence must be absent when slot_evidence_available is false"
            )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BenchmarkDecision":
        if not isinstance(payload, Mapping):
            raise BenchmarkSchemaError("adapter output must be a mapping")
        unknown = set(payload) - {"intent", "track", "artist", "album", "confidence", "option_scores"}
        forbidden = unknown & FORBIDDEN_RESULT_KEYS
        if forbidden:
            raise BenchmarkSchemaError(f"adapter output contains execution authority fields: {sorted(forbidden)}")
        if unknown:
            raise BenchmarkSchemaError(f"adapter output contains unknown fields: {sorted(unknown)}")
        if "intent" not in payload:
            raise BenchmarkSchemaError("adapter output is missing intent")
        return cls(
            intent=payload["intent"],
            track=payload.get("track"),
            artist=payload.get("artist"),
            album=payload.get("album"),
            confidence=payload.get("confidence"),
            option_scores=payload.get("option_scores", {}),
        )


class BenchmarkAdapter(Protocol):
    """Interface shared by strict-schema, option-scoring, and encoder routes."""

    route: AdapterRoute
    model_name: str

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        """Return evidence only; never a ValidatedAction or trusted entity."""


class CallableBenchmarkAdapter:
    """Small adapter seam for a future candidate-specific implementation."""

    def __init__(
        self,
        route: AdapterRoute,
        model_name: str,
        infer_fn: Callable[[BenchmarkRequest], Mapping[str, Any] | BenchmarkDecision],
    ) -> None:
        self.route = route
        self.model_name = _require_text("model_name", model_name)
        self._infer_fn = infer_fn

    def infer(self, request: BenchmarkRequest) -> BenchmarkDecision:
        value = self._infer_fn(request)
        if isinstance(value, BenchmarkDecision):
            return value
        return BenchmarkDecision.from_mapping(value)


@dataclass(frozen=True, slots=True)
class CaseObservation:
    """One sanitized case-level observation used for aggregate metrics."""

    case_id: str
    category: str
    ai_scope: str
    expected_intent: str
    actual_intent: str
    semantic_ok: bool
    inference_attempted: bool
    transport_ok: bool
    schema_ok: bool
    latency_ms: float | None = None
    malformed_output: bool = False
    timeout: bool = False
    backend_failure: bool = False
    false_execution: bool = False
    post_grounding_false_acceptance: bool = False
    language_slice: str | None = None
    probability: float | None = None
    probability_target: bool | None = None
    option_order_flipped: bool | None = None
    track_slot_ok: bool | None = None
    artist_slot_ok: bool | None = None
    album_slot_ok: bool | None = None
    error_type: str | None = None
    intent_ok: bool | None = None
    semantic_evaluated: bool = True
    slot_evidence_available: bool = True

    def __post_init__(self) -> None:
        _require_text("case_id", self.case_id)
        _require_text("category", self.category)
        if self.ai_scope not in ALLOWED_AI_SCOPES:
            raise BenchmarkSchemaError("ai_scope is invalid")
        if self.expected_intent not in ALLOWED_INTENTS or self.actual_intent not in ALLOWED_INTENTS:
            raise BenchmarkSchemaError("case intents are outside the benchmark allowlist")
        for name in (
            "semantic_ok",
            "inference_attempted",
            "transport_ok",
            "schema_ok",
            "malformed_output",
            "timeout",
            "backend_failure",
            "false_execution",
            "post_grounding_false_acceptance",
        ):
            _require_bool(name, getattr(self, name))
        for name in ("semantic_evaluated", "slot_evidence_available"):
            _require_bool(name, getattr(self, name))
        if self.intent_ok is not None and not isinstance(self.intent_ok, bool):
            raise BenchmarkSchemaError("intent_ok must be boolean or null")
        _require_nonnegative("latency_ms", self.latency_ms)
        if self.language_slice is not None and self.language_slice not in ALLOWED_LANGUAGE_SLICES:
            raise BenchmarkSchemaError("language_slice is invalid")
        _require_rate("probability", self.probability)
        if self.probability is not None and not isinstance(self.probability_target, bool):
            raise BenchmarkSchemaError("probability_target is required with probability")
        for name in ("probability_target", "option_order_flipped", "track_slot_ok", "artist_slot_ok", "album_slot_ok"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise BenchmarkSchemaError(f"{name} must be boolean or null")
        if self.error_type is not None:
            _require_text("error_type", self.error_type)


def _rate(items: Sequence[CaseObservation], predicate: Callable[[CaseObservation], bool]) -> float | None:
    if not items:
        return None
    return round(sum(predicate(item) for item in items) / len(items), 4)


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 1)


def _calibration_metrics(observations: Sequence[CaseObservation]) -> tuple[float | None, float | None]:
    pairs = [
        (float(item.probability), bool(item.probability_target))
        for item in observations
        if item.probability is not None and item.probability_target is not None
    ]
    if not pairs:
        return None, None
    brier = round(sum((probability - float(target)) ** 2 for probability, target in pairs) / len(pairs), 4)
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(10)]
    for probability, target in pairs:
        bins[min(9, int(probability * 10))].append((probability, target))
    ece = 0.0
    for bucket in bins:
        if bucket:
            confidence = sum(probability for probability, _ in bucket) / len(bucket)
            accuracy = sum(target for _, target in bucket) / len(bucket)
            ece += len(bucket) / len(pairs) * abs(confidence - accuracy)
    return brier, round(ece, 4)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Closed aggregate result schema; no raw model output or authority fields."""

    candidate_name: str
    model_name: str
    repository_revision: str
    model_revision: str
    backend: str
    precision: str
    quantization: str
    hardware_identity: str
    hardware_alignment_status: str
    quality_run_status: str
    route: str
    case_count: int
    supported_case_count: int
    candidate_model_evaluated_supported_case_count: int
    supported_expected_play_case_count: int
    supported_expected_unknown_case_count: int
    play_true_positive_count: int
    play_recall: float | None
    unknown_true_negative_count: int
    unknown_recall: float | None
    balanced_intent_accuracy: float | None
    deterministic_only_cases_not_sent_to_model: int
    safety_only_cases_not_sent_to_model: int
    model_load_success: bool
    transport_success_rate: float | None
    typed_output_schema_success_rate: float | None
    supported_semantic_accuracy: float | None
    supported_intent_accuracy: float | None
    entity_slot_evaluation_available: bool
    semantic_retry_accuracy: float | None
    semantic_retry_intent_accuracy: float | None
    deterministic_only_eligibility_gate_safe_unknown_rate: float | None
    safety_only_eligibility_gate_safe_unknown_rate: float | None
    false_execution_rate: float | None
    expected_unknown_false_accept_count: int
    expected_unknown_false_accept_rate: float | None
    expected_unknown_false_acceptance_incidence_rate: float | None
    post_grounding_false_acceptance_rate: float | None
    malformed_output_rate: float | None
    timeout_rate: float | None
    backend_failure_rate: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    throughput_per_second: float | None
    peak_vram_bytes: int | None
    peak_system_ram_bytes: int | None
    load_time_ms: float | None
    brier_score: float | None
    expected_calibration_error: float | None
    option_order_flip_rate: float | None
    language_slice_accuracy: Mapping[str, float] = field(default_factory=dict)
    language_slice_intent_accuracy: Mapping[str, float] = field(default_factory=dict)
    slot_accuracy: Mapping[str, float] = field(default_factory=dict)
    error_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "candidate_name",
            "model_name",
            "repository_revision",
            "model_revision",
            "backend",
            "precision",
            "quantization",
            "hardware_identity",
            "hardware_alignment_status",
            "quality_run_status",
            "route",
        ):
            _require_text(name, getattr(self, name))
        if isinstance(self.case_count, bool) or not isinstance(self.case_count, int) or self.case_count < 1:
            raise BenchmarkSchemaError("case_count must be a positive integer")
        for name in (
            "supported_case_count",
            "candidate_model_evaluated_supported_case_count",
            "supported_expected_play_case_count",
            "supported_expected_unknown_case_count",
            "play_true_positive_count",
            "unknown_true_negative_count",
            "deterministic_only_cases_not_sent_to_model",
            "safety_only_cases_not_sent_to_model",
            "expected_unknown_false_accept_count",
        ):
            _require_count(name, getattr(self, name))
        if self.supported_case_count > self.case_count:
            raise BenchmarkSchemaError("supported_case_count cannot exceed case_count")
        if self.candidate_model_evaluated_supported_case_count > self.supported_case_count:
            raise BenchmarkSchemaError(
                "candidate_model_evaluated_supported_case_count cannot exceed supported_case_count"
            )
        if (
            self.supported_expected_play_case_count + self.supported_expected_unknown_case_count
            > self.supported_case_count
        ):
            raise BenchmarkSchemaError("supported intent class counts cannot exceed supported_case_count")
        if self.play_true_positive_count > self.supported_expected_play_case_count:
            raise BenchmarkSchemaError("play_true_positive_count exceeds expected play count")
        if self.unknown_true_negative_count > self.supported_expected_unknown_case_count:
            raise BenchmarkSchemaError("unknown_true_negative_count exceeds expected unknown count")
        if self.expected_unknown_false_accept_count > self.supported_expected_unknown_case_count:
            raise BenchmarkSchemaError("expected unknown false accepts exceed expected unknown count")
        _require_bool("model_load_success", self.model_load_success)
        _require_bool("entity_slot_evaluation_available", self.entity_slot_evaluation_available)
        for name in (
            "transport_success_rate",
            "typed_output_schema_success_rate",
            "supported_semantic_accuracy",
            "semantic_retry_accuracy",
            "play_recall",
            "unknown_recall",
            "balanced_intent_accuracy",
            "deterministic_only_eligibility_gate_safe_unknown_rate",
            "safety_only_eligibility_gate_safe_unknown_rate",
            "false_execution_rate",
            "expected_unknown_false_accept_rate",
            "expected_unknown_false_acceptance_incidence_rate",
            "post_grounding_false_acceptance_rate",
            "malformed_output_rate",
            "timeout_rate",
            "backend_failure_rate",
            "brier_score",
            "expected_calibration_error",
            "option_order_flip_rate",
        ):
            _require_rate(name, getattr(self, name))
        for name in ("p50_latency_ms", "p95_latency_ms", "throughput_per_second", "load_time_ms"):
            _require_nonnegative(name, getattr(self, name))
        for name in ("peak_vram_bytes", "peak_system_ram_bytes"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise BenchmarkSchemaError(f"{name} must be a non-negative integer or null")
        for name in ("language_slice_accuracy", "language_slice_intent_accuracy", "slot_accuracy"):
            values = getattr(self, name)
            if not isinstance(values, Mapping):
                raise BenchmarkSchemaError(f"{name} must be a mapping")
            for key, value in values.items():
                _require_text(f"{name} key", key)
                _require_rate(f"{name}[{key}]", value)
        if not isinstance(self.error_counts, Mapping):
            raise BenchmarkSchemaError("error_counts must be a mapping")
        for key, value in self.error_counts.items():
            _require_text("error_counts key", key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise BenchmarkSchemaError("error_counts values must be non-negative integers")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["language_slice_accuracy"] = dict(self.language_slice_accuracy)
        payload["language_slice_intent_accuracy"] = dict(self.language_slice_intent_accuracy)
        payload["slot_accuracy"] = dict(self.slot_accuracy)
        payload["error_counts"] = dict(self.error_counts)
        return payload

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BenchmarkResult":
        if not isinstance(payload, Mapping):
            raise BenchmarkSchemaError("benchmark result must be a mapping")
        expected = {item.name for item in fields(cls)}
        actual = set(payload)
        extra = actual - expected
        forbidden = extra & FORBIDDEN_RESULT_KEYS
        if forbidden:
            raise BenchmarkSchemaError(f"result contains execution authority fields: {sorted(forbidden)}")
        if extra:
            raise BenchmarkSchemaError(f"result contains unknown fields: {sorted(extra)}")
        missing = expected - actual
        if missing:
            raise BenchmarkSchemaError(f"result is missing fields: {sorted(missing)}")
        return cls(**dict(payload))


def aggregate_observations(
    metadata: Mapping[str, Any],
    observations: Sequence[CaseObservation],
    *,
    model_load_success: bool,
    throughput_per_second: float | None = None,
    peak_vram_bytes: int | None = None,
    peak_system_ram_bytes: int | None = None,
    load_time_ms: float | None = None,
) -> BenchmarkResult:
    """Aggregate sanitized case observations into the common result schema."""

    if not observations:
        raise BenchmarkSchemaError("at least one case observation is required")
    case_ids = [item.case_id for item in observations]
    if len(set(case_ids)) != len(case_ids):
        raise BenchmarkSchemaError("case observations must have unique case IDs")
    required_metadata = (
        "candidate_name",
        "model_name",
        "repository_revision",
        "model_revision",
        "backend",
        "precision",
        "quantization",
        "hardware_identity",
        "hardware_alignment_status",
        "quality_run_status",
        "route",
    )
    for key in required_metadata:
        _require_text(key, metadata.get(key))
    attempted = [item for item in observations if item.inference_attempted]
    supported = [item for item in observations if item.ai_scope == "supported"]
    semantic_supported = [item for item in supported if item.semantic_evaluated]
    intent_supported = [item for item in supported if item.intent_ok is not None]
    expected_play = [
        item for item in supported if item.expected_intent == "spotify_play_track"
    ]
    expected_unknown = [item for item in supported if item.expected_intent == "unknown"]
    play_true_positive_count = sum(item.intent_ok is True for item in expected_play)
    unknown_true_negative_count = sum(item.intent_ok is True for item in expected_unknown)
    expected_unknown_false_accept_count = sum(
        item.intent_ok is not None and item.actual_intent != "unknown"
        for item in expected_unknown
    )
    retry = [
        item for item in observations if item.category == "semantic_retry" and item.semantic_evaluated
    ]
    retry_intent = [
        item for item in observations if item.category == "semantic_retry" and item.intent_ok is not None
    ]
    deterministic = [
        item
        for item in observations
        if item.ai_scope == "deterministic_only" and not item.inference_attempted
    ]
    safety = [
        item
        for item in observations
        if item.ai_scope == "safety_only" and not item.inference_attempted
    ]
    grounding_supported = [
        item for item in semantic_supported if item.slot_evidence_available
    ]
    latencies = [item.latency_ms for item in attempted if item.latency_ms is not None]
    brier, ece = _calibration_metrics(observations)

    play_recall = _rate(expected_play, lambda item: item.intent_ok is True)
    unknown_recall = _rate(expected_unknown, lambda item: item.intent_ok is True)
    balanced_intent_accuracy = (
        round((play_recall + unknown_recall) / 2, 4)
        if play_recall is not None and unknown_recall is not None
        else None
    )
    expected_unknown_false_accept_rate = _rate(
        expected_unknown,
        lambda item: item.intent_ok is not None and item.actual_intent != "unknown",
    )
    expected_unknown_false_acceptance_incidence_rate = (
        round(expected_unknown_false_accept_count / len(observations), 4)
        if observations
        else None
    )

    language_metrics: dict[str, float] = {}
    for language in sorted({item.language_slice for item in semantic_supported if item.language_slice}):
        language_rows = [item for item in semantic_supported if item.language_slice == language]
        accuracy = _rate(language_rows, lambda item: item.semantic_ok)
        if accuracy is not None:
            language_metrics[language] = accuracy

    language_intent_metrics: dict[str, float] = {}
    for language in sorted({item.language_slice for item in intent_supported if item.language_slice}):
        language_rows = [item for item in intent_supported if item.language_slice == language]
        accuracy = _rate(language_rows, lambda item: bool(item.intent_ok))
        if accuracy is not None:
            language_intent_metrics[language] = accuracy

    slot_metrics: dict[str, float] = {}
    for name, attribute in (
        ("track", "track_slot_ok"),
        ("artist", "artist_slot_ok"),
        ("album", "album_slot_ok"),
    ):
        slot_rows = [item for item in grounding_supported if getattr(item, attribute) is not None]
        accuracy = _rate(slot_rows, lambda item, attr=attribute: bool(getattr(item, attr)))
        if accuracy is not None:
            slot_metrics[name] = accuracy

    errors: dict[str, int] = {}
    for item in observations:
        if item.error_type:
            errors[item.error_type] = errors.get(item.error_type, 0) + 1

    return BenchmarkResult(
        candidate_name=str(metadata["candidate_name"]),
        model_name=str(metadata["model_name"]),
        repository_revision=str(metadata["repository_revision"]),
        model_revision=str(metadata["model_revision"]),
        backend=str(metadata["backend"]),
        precision=str(metadata["precision"]),
        quantization=str(metadata["quantization"]),
        hardware_identity=str(metadata["hardware_identity"]),
        hardware_alignment_status=str(metadata["hardware_alignment_status"]),
        quality_run_status=str(metadata["quality_run_status"]),
        route=str(metadata["route"]),
        case_count=len(observations),
        supported_case_count=len(supported),
        candidate_model_evaluated_supported_case_count=len(intent_supported),
        supported_expected_play_case_count=len(expected_play),
        supported_expected_unknown_case_count=len(expected_unknown),
        play_true_positive_count=play_true_positive_count,
        play_recall=play_recall,
        unknown_true_negative_count=unknown_true_negative_count,
        unknown_recall=unknown_recall,
        balanced_intent_accuracy=balanced_intent_accuracy,
        deterministic_only_cases_not_sent_to_model=len(deterministic),
        safety_only_cases_not_sent_to_model=len(safety),
        model_load_success=model_load_success,
        transport_success_rate=_rate(attempted, lambda item: item.transport_ok),
        typed_output_schema_success_rate=_rate(attempted, lambda item: item.schema_ok),
        supported_semantic_accuracy=_rate(semantic_supported, lambda item: item.semantic_ok),
        supported_intent_accuracy=_rate(intent_supported, lambda item: bool(item.intent_ok)),
        entity_slot_evaluation_available=bool(grounding_supported),
        semantic_retry_accuracy=_rate(retry, lambda item: item.semantic_ok),
        semantic_retry_intent_accuracy=_rate(retry_intent, lambda item: bool(item.intent_ok)),
        deterministic_only_eligibility_gate_safe_unknown_rate=_rate(
            deterministic,
            lambda item: item.actual_intent == "unknown" and not item.false_execution,
        ),
        safety_only_eligibility_gate_safe_unknown_rate=_rate(
            safety,
            lambda item: item.actual_intent == "unknown" and not item.false_execution,
        ),
        false_execution_rate=_rate(observations, lambda item: item.false_execution),
        expected_unknown_false_accept_count=expected_unknown_false_accept_count,
        expected_unknown_false_accept_rate=expected_unknown_false_accept_rate,
        expected_unknown_false_acceptance_incidence_rate=expected_unknown_false_acceptance_incidence_rate,
        post_grounding_false_acceptance_rate=_rate(
            grounding_supported, lambda item: item.post_grounding_false_acceptance
        ),
        malformed_output_rate=_rate(attempted, lambda item: item.malformed_output),
        timeout_rate=_rate(attempted, lambda item: item.timeout),
        backend_failure_rate=_rate(attempted, lambda item: item.backend_failure),
        p50_latency_ms=round(float(median(latencies)), 1) if latencies else None,
        p95_latency_ms=_percentile(latencies, 0.95),
        throughput_per_second=throughput_per_second,
        peak_vram_bytes=peak_vram_bytes,
        peak_system_ram_bytes=peak_system_ram_bytes,
        load_time_ms=load_time_ms,
        brier_score=brier,
        expected_calibration_error=ece,
        option_order_flip_rate=_rate(
            [item for item in observations if item.option_order_flipped is not None],
            lambda item: bool(item.option_order_flipped),
        ),
        language_slice_accuracy=language_metrics,
        language_slice_intent_accuracy=language_intent_metrics,
        slot_accuracy=slot_metrics,
        error_counts=errors,
    )


def benchmark_artifact_root(repo_root: Path = REPO_ROOT) -> Path:
    """Return the already-ignored root for raw local benchmark artifacts."""

    return repo_root / "runtime" / "ai_poc"


def artifact_directory(name: str, repo_root: Path = REPO_ROOT) -> Path:
    """Resolve a safe artifact directory below the ignored benchmark root."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name):
        raise ValueError("artifact directory name is invalid")
    root = benchmark_artifact_root(repo_root).resolve()
    target = (root / name).resolve()
    if target.parent != root:
        raise ValueError("artifact directory escaped the benchmark root")
    return target
