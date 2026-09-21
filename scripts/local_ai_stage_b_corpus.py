"""Offline, benchmark-only Stage B corpus schema and validation.

This module turns the reviewed Stage B protocol into machine-verifiable
invariants.  It intentionally has no imports from ``app`` and no network,
subprocess, model, Spotify, LM Studio, or Windows execution path.

The module validates sanitized corpus records and produces deterministic
manifest/count/hash evidence.  It does not generate a corpus, train a model,
run inference, or create a production action.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE_A_CORPUS_PATH = REPO_ROOT / "tests" / "fixtures" / "ai_intent_cases.json"
EXPECTED_STAGE_A_CASE_COUNT = 109
EXPECTED_STAGE_A_SHA256 = "60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55"

SCHEMA_VERSION = 1
SPLIT_NAMES = ("train", "validation", "test")
HELD_OUT_SPLIT = "test"
SPLIT_ALIASES = {
    "held_out": HELD_OUT_SPLIT,
    "held-out": HELD_OUT_SPLIT,
    "held_out_test": HELD_OUT_SPLIT,
}

EXPECTED_SPLIT_COUNTS: dict[str, dict[str, int]] = {
    "train": {
        "supported_play": 900,
        "supported_unknown": 600,
        "deterministic_only": 180,
        "safety_only": 120,
        "total": 1800,
    },
    "validation": {
        "supported_play": 300,
        "supported_unknown": 240,
        "deterministic_only": 30,
        "safety_only": 30,
        "total": 600,
    },
    "test": {
        "supported_play": 300,
        "supported_unknown": 240,
        "deterministic_only": 30,
        "safety_only": 30,
        "total": 600,
    },
}

OPTIONAL_SLOT_NAMES = ("artist", "album")
OPTIONAL_SLOT_MINIMUMS = {
    "artist_present_rows": 150,
    "artist_absent_rows": 100,
    "album_present_rows": 100,
    "album_absent_rows": 150,
}


class StageBIntent(str, Enum):
    SPOTIFY_PLAY_TRACK = "spotify_play_track"
    UNKNOWN = "unknown"


class StageBAIScope(str, Enum):
    SUPPORTED = "supported"
    DETERMINISTIC_ONLY = "deterministic_only"
    SAFETY_ONLY = "safety_only"


class StageBLanguageTag(str, Enum):
    ZH_HANT = "zh-Hant"
    ZH_HANS = "zh-Hans"
    EN = "en"
    MIXED = "mixed"


class StageBLanguageSlice(str, Enum):
    CHINESE = "chinese"
    ENGLISH = "english"
    MIXED = "mixed"


class OptionalSlotStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"


class NegativeReason(str, Enum):
    MISSING_TRACK = "missing_track"
    ARTIST_ONLY = "artist_only"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    AMBIGUOUS_VERSION = "ambiguous_version"
    UNSUPPORTED_DOMAIN = "unsupported_domain"
    PLAYBACK_CONTROL = "playback_control"
    HOSTILE_SYSTEM = "hostile_system"
    PATH_OR_URL = "path_or_url"
    MALFORMED_INPUT = "malformed_input"


ALLOWED_LANGUAGE_SLICE_BY_TAG = {
    StageBLanguageTag.ZH_HANT.value: StageBLanguageSlice.CHINESE.value,
    StageBLanguageTag.ZH_HANS.value: StageBLanguageSlice.CHINESE.value,
    StageBLanguageTag.EN.value: StageBLanguageSlice.ENGLISH.value,
    StageBLanguageTag.MIXED.value: StageBLanguageSlice.MIXED.value,
}

TOP_LEVEL_FIELDS = frozenset(
    {
        "case_id",
        "source_group_id",
        "utterance",
        "language_tag",
        "language_slice",
        "ai_scope",
        "expected",
        "optional_slot_status",
        "negative_reason",
        "template_family",
        "generator_version",
    }
)
EXPECTED_FIELDS = frozenset({"intent", "track", "artist", "album"})
SPAN_FIELDS = frozenset({"text", "start", "end"})
OPTIONAL_SLOT_STATUS_FIELDS = frozenset(OPTIONAL_SLOT_NAMES)

# These are field names, not text patterns.  A hostile utterance may contain
# a path or URL as a reviewed negative example; it must not become a field
# carrying an execution target.
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "action",
        "access_token",
        "access_tokens",
        "api_key",
        "api_keys",
        "catalog",
        "catalog_object",
        "clarification_token",
        "cmd",
        "command",
        "confirmation_token",
        "credential",
        "credentials",
        "executable_path",
        "filesystem_path",
        "oauth",
        "oauth_token",
        "powershell",
        "process_id",
        "refresh_token",
        "refresh_tokens",
        "shell",
        "spotify_uri",
        "track_id",
        "trusted_catalog_object",
        "url",
        "validated_action",
    }
)


class StageBCorpusError(ValueError):
    """Base class for bounded Stage B corpus validation failures."""


class StageBSchemaError(StageBCorpusError):
    """A record is not a valid closed Stage B schema object."""


class StageBProtocolError(StageBCorpusError):
    """A valid record set violates the frozen protocol counts or gates."""


class StageBLeakageError(StageBCorpusError):
    """A record set violates frozen Stage A or split leakage boundaries."""


class StageBManifestError(StageBCorpusError):
    """A manifest input is not suitable for deterministic identity generation."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    """Return the stable UTF-8 JSON representation used for hashing."""

    return _canonical_json_bytes(value).decode("utf-8")


def _key_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _is_forbidden_field(name: str) -> bool:
    token = _key_token(name)
    if token in FORBIDDEN_FIELD_NAMES:
        return True
    if token.endswith(("_token", "_tokens", "_secret", "_secrets")):
        return True
    if (
        "oauth" in token
        or "access_token" in token
        or "access_tokens" in token
        or "refresh_token" in token
        or "refresh_tokens" in token
        or "api_key" in token
        or "api_keys" in token
    ):
        return True
    if "trusted_catalog" in token or "validated_action" in token:
        return True
    return False


def _scan_forbidden_fields(value: Any, path: str = "record") -> None:
    """Reject authority-bearing keys without echoing untrusted values."""

    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise StageBSchemaError(f"{path} contains a non-text field name")
            if _is_forbidden_field(key):
                raise StageBSchemaError(f"{path}.{_key_token(key)} is forbidden")
            _scan_forbidden_fields(nested, f"{path}.{_key_token(key)}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _scan_forbidden_fields(nested, f"{path}[{index}]")


_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)spotify:[a-z0-9_-]+:[a-z0-9_-]+"),
    re.compile(r"(?i)https?://"),
    re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\)"),
    re.compile(r"(?i)\b(?:bearer|oauth|api[ _-]?key|access[ _-]?token|refresh[ _-]?token)\b"),
)


def _scan_sensitive_values(value: Any, path: str = "record") -> None:
    """Reject URI/path/token values outside the reviewed raw utterance."""

    if path == "record.utterance":
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _scan_sensitive_values(nested, f"{path}.{_key_token(key)}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _scan_sensitive_values(nested, f"{path}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS):
        raise StageBSchemaError(f"{path} contains forbidden sensitive material")


def _require_text(name: str, value: Any, *, max_length: int, allow_blank: bool = False) -> str:
    if not isinstance(value, str):
        raise StageBSchemaError(f"{name} must be text")
    if len(value) > max_length:
        raise StageBSchemaError(f"{name} exceeds its bound")
    if not allow_blank and not value.strip():
        raise StageBSchemaError(f"{name} must be non-empty")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise StageBSchemaError(f"{name} contains a control character")
    return value


def _require_integer(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StageBSchemaError(f"{name} must be an integer")
    return value


def _require_exact_keys(mapping: Mapping[str, Any], expected: frozenset[str], name: str) -> None:
    keys = set(mapping)
    missing = expected - keys
    extra = keys - expected
    if missing:
        raise StageBSchemaError(f"{name} is missing required fields")
    if extra:
        raise StageBSchemaError(f"{name} contains unknown fields")


def _enum_text(name: str, value: Any, enum_type: type[Enum]) -> str:
    if not isinstance(value, str):
        raise StageBSchemaError(f"{name} must use an approved value")
    allowed = {member.value for member in enum_type}
    if value not in allowed:
        raise StageBSchemaError(f"{name} is outside the closed enum")
    return value


@dataclass(frozen=True, slots=True)
class StageBSpan:
    """A source-text span with Python code-point offsets."""

    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass(frozen=True, slots=True)
class StageBExpected:
    intent: str
    track: StageBSpan | None
    artist: StageBSpan | None
    album: StageBSpan | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "track": self.track.to_dict() if self.track is not None else None,
            "artist": self.artist.to_dict() if self.artist is not None else None,
            "album": self.album.to_dict() if self.album is not None else None,
        }


@dataclass(frozen=True, slots=True)
class StageBRecord:
    case_id: str
    source_group_id: str
    utterance: str
    language_tag: str
    language_slice: str
    ai_scope: str
    expected: StageBExpected
    optional_slot_status: Mapping[str, str] | None
    negative_reason: str | None
    template_family: str
    generator_version: str

    def __post_init__(self) -> None:
        _require_text("case_id", self.case_id, max_length=200)
        _require_text("source_group_id", self.source_group_id, max_length=200)
        _require_text("utterance", self.utterance, max_length=4000)
        _require_text("template_family", self.template_family, max_length=200)
        _require_text("generator_version", self.generator_version, max_length=200)
        if not isinstance(self.expected, StageBExpected):
            raise StageBSchemaError("expected must be a StageBExpected")
        if self.language_tag not in {member.value for member in StageBLanguageTag}:
            raise StageBSchemaError("language_tag is outside the closed enum")
        if self.language_slice not in {member.value for member in StageBLanguageSlice}:
            raise StageBSchemaError("language_slice is outside the closed enum")
        if self.language_slice != ALLOWED_LANGUAGE_SLICE_BY_TAG[self.language_tag]:
            raise StageBSchemaError("language_tag and language_slice mapping is inconsistent")
        if self.ai_scope not in {member.value for member in StageBAIScope}:
            raise StageBSchemaError("ai_scope is outside the closed enum")
        if not isinstance(self.expected.intent, str) or self.expected.intent not in {
            member.value for member in StageBIntent
        }:
            raise StageBSchemaError("expected.intent is outside the closed enum")
        if self.negative_reason is not None:
            if not isinstance(self.negative_reason, str) or self.negative_reason not in {
                member.value for member in NegativeReason
            }:
                raise StageBSchemaError("negative_reason is outside the closed enum")
        if self.optional_slot_status is not None:
            if not isinstance(self.optional_slot_status, Mapping):
                raise StageBSchemaError("optional_slot_status must be an object or null")
            if set(self.optional_slot_status) != OPTIONAL_SLOT_STATUS_FIELDS:
                raise StageBSchemaError("optional_slot_status must contain exactly artist and album")
            for field in OPTIONAL_SLOT_NAMES:
                status = self.optional_slot_status[field]
                if not isinstance(status, str) or status not in {
                    member.value for member in OptionalSlotStatus
                }:
                    raise StageBSchemaError("optional_slot_status contains an unapproved value")
        _validate_span_relationships(self.utterance, self.expected)
        _validate_record_semantics(self)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StageBRecord":
        if not isinstance(payload, Mapping):
            raise StageBSchemaError("record must be an object")
        _scan_forbidden_fields(payload)
        _scan_sensitive_values(payload)
        _require_exact_keys(payload, TOP_LEVEL_FIELDS, "record")

        utterance = _require_text("utterance", payload["utterance"], max_length=4000)
        if not isinstance(payload["expected"], Mapping):
            raise StageBSchemaError("expected must be an object")
        expected_payload = payload["expected"]
        _require_exact_keys(expected_payload, EXPECTED_FIELDS, "expected")

        def parse_span(field: str) -> StageBSpan | None:
            value = expected_payload[field]
            if value is None:
                return None
            if not isinstance(value, Mapping):
                raise StageBSchemaError(f"expected.{field} must be an object or null")
            _require_exact_keys(value, SPAN_FIELDS, f"expected.{field}")
            text = _require_text(f"expected.{field}.text", value["text"], max_length=300)
            start = _require_integer(f"expected.{field}.start", value["start"])
            end = _require_integer(f"expected.{field}.end", value["end"])
            if start < 0 or end < 0:
                raise StageBSchemaError(f"expected.{field} offsets must not be negative")
            if end <= start:
                raise StageBSchemaError(f"expected.{field} end must be greater than start")
            if end > len(utterance):
                raise StageBSchemaError(f"expected.{field} offset exceeds utterance")
            if utterance[start:end] != text:
                raise StageBSchemaError(f"expected.{field} does not match the original utterance")
            return StageBSpan(text=text, start=start, end=end)

        expected = StageBExpected(
            intent=_enum_text("expected.intent", expected_payload["intent"], StageBIntent),
            track=parse_span("track"),
            artist=parse_span("artist"),
            album=parse_span("album"),
        )

        status_value = payload["optional_slot_status"]
        optional_slot_status: dict[str, str] | None
        if status_value is None:
            optional_slot_status = None
        else:
            if not isinstance(status_value, Mapping):
                raise StageBSchemaError("optional_slot_status must be an object or null")
            _require_exact_keys(status_value, OPTIONAL_SLOT_STATUS_FIELDS, "optional_slot_status")
            optional_slot_status = {
                field: _enum_text(
                    f"optional_slot_status.{field}",
                    status_value[field],
                    OptionalSlotStatus,
                )
                for field in OPTIONAL_SLOT_NAMES
            }

        negative_reason = payload["negative_reason"]
        if negative_reason is not None:
            negative_reason = _enum_text("negative_reason", negative_reason, NegativeReason)

        return cls(
            case_id=_require_text("case_id", payload["case_id"], max_length=200),
            source_group_id=_require_text(
                "source_group_id", payload["source_group_id"], max_length=200
            ),
            utterance=utterance,
            language_tag=_enum_text("language_tag", payload["language_tag"], StageBLanguageTag),
            language_slice=_enum_text(
                "language_slice", payload["language_slice"], StageBLanguageSlice
            ),
            ai_scope=_enum_text("ai_scope", payload["ai_scope"], StageBAIScope),
            expected=expected,
            optional_slot_status=optional_slot_status,
            negative_reason=negative_reason,
            template_family=_require_text(
                "template_family", payload["template_family"], max_length=200
            ),
            generator_version=_require_text(
                "generator_version", payload["generator_version"], max_length=200
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "source_group_id": self.source_group_id,
            "utterance": self.utterance,
            "language_tag": self.language_tag,
            "language_slice": self.language_slice,
            "ai_scope": self.ai_scope,
            "expected": self.expected.to_dict(),
            "optional_slot_status": (
                dict(self.optional_slot_status) if self.optional_slot_status is not None else None
            ),
            "negative_reason": self.negative_reason,
            "template_family": self.template_family,
            "generator_version": self.generator_version,
        }


def _validate_span_relationships(utterance: str, expected: StageBExpected) -> None:
    spans: list[tuple[str, StageBSpan]] = []
    for field in ("track", "artist", "album"):
        span = getattr(expected, field)
        if span is None:
            continue
        if not isinstance(span, StageBSpan):
            raise StageBSchemaError(f"expected.{field} must be a StageBSpan or null")
        _require_text(f"expected.{field}.text", span.text, max_length=300)
        start = _require_integer(f"expected.{field}.start", span.start)
        end = _require_integer(f"expected.{field}.end", span.end)
        spans.append((field, StageBSpan(span.text, start, end)))
    ordered = sorted(spans, key=lambda item: (item[1].start, item[1].end, item[0]))
    for previous, current in zip(ordered, ordered[1:]):
        if previous[1].end > current[1].start:
            raise StageBSchemaError("track, artist, and album spans must not overlap")
    for field, span in spans:
        if span.start < 0 or span.end <= span.start or span.end > len(utterance):
            raise StageBSchemaError(f"expected.{field} has an impossible span")
        if utterance[span.start : span.end] != span.text:
            raise StageBSchemaError(f"expected.{field} does not match the original utterance")


def _validate_record_semantics(record: StageBRecord) -> None:
    expected = record.expected
    is_supported = record.ai_scope == StageBAIScope.SUPPORTED.value
    is_positive = expected.intent == StageBIntent.SPOTIFY_PLAY_TRACK.value

    if not is_supported:
        if is_positive:
            raise StageBSchemaError("deterministic-only and safety-only rows must be unknown")
        if any(getattr(expected, field) is not None for field in ("track", "artist", "album")):
            raise StageBSchemaError("non-supported rows cannot carry output slots")
        if record.optional_slot_status is not None:
            raise StageBSchemaError("non-supported rows do not enter the optional-slot partition")
        return

    if is_positive:
        if expected.track is None:
            raise StageBSchemaError("supported spotify_play_track requires a track span")
        if record.negative_reason is not None:
            raise StageBSchemaError("supported positive rows must have null negative_reason")
        if record.optional_slot_status is None:
            raise StageBSchemaError("supported positive rows require optional_slot_status")
        for field in OPTIONAL_SLOT_NAMES:
            span_present = getattr(expected, field) is not None
            status_present = record.optional_slot_status[field] == OptionalSlotStatus.PRESENT.value
            if span_present != status_present:
                label = "present" if status_present else "absent"
                raise StageBSchemaError(f"{field} span nullability disagrees with {label} status")
        return

    if any(getattr(expected, field) is not None for field in ("track", "artist", "album")):
        raise StageBSchemaError("supported unknown rows cannot carry output slots")
    if record.optional_slot_status is not None:
        raise StageBSchemaError("supported unknown rows do not enter the optional-slot partition")


def canonicalize_for_comparison(text: str) -> str:
    """Normalize only for duplicate comparison; never rewrite stored text.

    The frozen comparison rule is NFKC, Unicode casefold, punctuation-to-space,
    whitespace collapse, and trim.  Traditional/Simplified conversion is
    intentionally not performed because no pinned conversion dependency is
    part of this infrastructure.
    """

    if not isinstance(text, str):
        raise StageBSchemaError("comparison text must be text")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    comparison_chars = []
    for character in normalized:
        if character.isspace() or unicodedata.category(character).startswith("P"):
            comparison_chars.append(" ")
        else:
            comparison_chars.append(character)
    return " ".join("".join(comparison_chars).split())


def _canonical_record_sort_key(record: StageBRecord) -> tuple[str, str, str, str]:
    return (
        record.case_id,
        record.source_group_id,
        canonicalize_for_comparison(record.utterance),
        canonical_json(record.to_dict()),
    )


def _canonical_records(records: Sequence[StageBRecord]) -> list[dict[str, Any]]:
    return [record.to_dict() for record in sorted(records, key=_canonical_record_sort_key)]


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _normalize_split_name(name: Any) -> str:
    if not isinstance(name, str):
        raise StageBManifestError("split names must be text")
    canonical = SPLIT_ALIASES.get(name, name)
    if canonical not in SPLIT_NAMES:
        raise StageBManifestError("split name is outside the frozen split set")
    return canonical


def _coerce_splits(
    splits: Mapping[str, Sequence[StageBRecord | Mapping[str, Any]]],
) -> dict[str, tuple[StageBRecord, ...]]:
    if not isinstance(splits, Mapping):
        raise StageBManifestError("splits must be an object keyed by split name")
    normalized: dict[str, tuple[StageBRecord, ...]] = {}
    for raw_name, raw_records in splits.items():
        name = _normalize_split_name(raw_name)
        if name in normalized:
            raise StageBManifestError("the same canonical split was supplied more than once")
        if isinstance(raw_records, (str, bytes)) or not isinstance(raw_records, Iterable):
            raise StageBManifestError("split rows must be an iterable of records")
        records: list[StageBRecord] = []
        for row in raw_records:
            records.append(row if isinstance(row, StageBRecord) else StageBRecord.from_mapping(row))
        normalized[name] = tuple(records)
    if not normalized:
        raise StageBManifestError("at least one split is required")
    return {name: normalized[name] for name in SPLIT_NAMES if name in normalized}


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageBCorpusError("cannot read corpus JSON") from exc
    if not isinstance(payload, list) or any(not isinstance(row, Mapping) for row in payload):
        raise StageBCorpusError("corpus JSON must be an array of objects")
    return list(payload)


def stage_a_identity(path: Path = DEFAULT_STAGE_A_CORPUS_PATH) -> dict[str, Any]:
    """Return only the frozen Stage A row count and content hash."""

    payload = _read_json_array(Path(path))
    return {"case_count": len(payload), "sha256": _sha256_json(payload)}


def _stage_a_utterances(
    path: Path,
    *,
    verify_frozen_identity: bool,
) -> set[str]:
    payload = _read_json_array(path)
    digest = _sha256_json(payload)
    if verify_frozen_identity and (
        len(payload) != EXPECTED_STAGE_A_CASE_COUNT or digest != EXPECTED_STAGE_A_SHA256
    ):
        raise StageBLeakageError("the frozen Stage A corpus identity does not match")
    utterances: set[str] = set()
    for row in payload:
        value = row.get("input")
        if isinstance(value, str):
            utterances.add(canonicalize_for_comparison(value))
    return utterances


def load_stage_a_utterances(
    path: Path = DEFAULT_STAGE_A_CORPUS_PATH,
    *,
    verify_frozen_identity: bool | None = None,
) -> set[str]:
    """Load only Stage A utterance identities for leakage detection.

    The default fixture is hash/count checked.  A custom test fixture is read
    for leakage tests without being treated as the frozen Stage A artifact.
    """

    resolved = Path(path).resolve()
    default_resolved = DEFAULT_STAGE_A_CORPUS_PATH.resolve()
    verify = resolved == default_resolved if verify_frozen_identity is None else verify_frozen_identity
    return _stage_a_utterances(resolved, verify_frozen_identity=verify)


def _entity_intent_template_key(record: StageBRecord) -> tuple[Any, ...] | None:
    if record.ai_scope != StageBAIScope.SUPPORTED.value:
        return None
    if record.expected.intent != StageBIntent.SPOTIFY_PLAY_TRACK.value:
        return None
    spans = tuple(
        canonicalize_for_comparison(getattr(record.expected, field).text)
        if getattr(record.expected, field) is not None
        else None
        for field in ("track", "artist", "album")
    )
    return (record.expected.intent, record.template_family, *spans)


def _validate_cross_split_boundaries(
    records_by_split: Mapping[str, Sequence[StageBRecord]],
    *,
    stage_a_utterances: set[str] | None,
) -> None:
    case_ids: dict[str, str] = {}
    groups: dict[str, str] = {}
    utterances: dict[str, str] = {}
    entity_groups: dict[tuple[Any, ...], str] = {}

    for split, records in records_by_split.items():
        for record in records:
            if record.case_id in case_ids:
                raise StageBLeakageError("case_id must be unique across all splits")
            case_ids[record.case_id] = split

            previous_group_split = groups.get(record.source_group_id)
            if previous_group_split is not None and previous_group_split != split:
                raise StageBLeakageError("source_group_id may not cross splits")
            groups[record.source_group_id] = split

            normalized_utterance = canonicalize_for_comparison(record.utterance)
            if normalized_utterance in utterances:
                raise StageBLeakageError("exact canonical utterances may not be duplicated")
            utterances[normalized_utterance] = split
            if stage_a_utterances is not None and normalized_utterance in stage_a_utterances:
                raise StageBLeakageError("Stage A utterance leakage detected")

            entity_key = _entity_intent_template_key(record)
            if entity_key is not None:
                previous_entity_split = entity_groups.get(entity_key)
                if previous_entity_split is not None and previous_entity_split != split:
                    raise StageBLeakageError(
                        "exact canonical entity/intent/template groups may not cross splits"
                    )
                entity_groups[entity_key] = split


def _class_counts(records: Sequence[StageBRecord]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        if record.ai_scope == StageBAIScope.SUPPORTED.value:
            key = (
                "supported_play"
                if record.expected.intent == StageBIntent.SPOTIFY_PLAY_TRACK.value
                else "supported_unknown"
            )
        else:
            key = record.ai_scope
        counts[key] += 1
    return counts


def optional_slot_partition(
    records: Sequence[StageBRecord],
    *,
    require_protocol_partition: bool = False,
) -> dict[str, int]:
    """Return exact held-out optional-slot counts.

    When ``require_protocol_partition`` is true, the frozen 300-row test
    partition and all coverage minima are enforced.  Smaller synthetic fixtures
    can use the default false mode while still validating every row's status
    and span agreement through ``StageBRecord``.
    """

    supported_play = [
        record
        for record in records
        if record.ai_scope == StageBAIScope.SUPPORTED.value
        and record.expected.intent == StageBIntent.SPOTIFY_PLAY_TRACK.value
    ]
    counts = {
        "supported_play_rows": len(supported_play),
        "artist_present_rows": sum(
            record.optional_slot_status["artist"] == OptionalSlotStatus.PRESENT.value
            for record in supported_play
        ),
        "artist_absent_rows": sum(
            record.optional_slot_status["artist"] == OptionalSlotStatus.ABSENT.value
            for record in supported_play
        ),
        "album_present_rows": sum(
            record.optional_slot_status["album"] == OptionalSlotStatus.PRESENT.value
            for record in supported_play
        ),
        "album_absent_rows": sum(
            record.optional_slot_status["album"] == OptionalSlotStatus.ABSENT.value
            for record in supported_play
        ),
    }
    if require_protocol_partition:
        if counts["supported_play_rows"] != 300:
            raise StageBProtocolError("held-out supported-play partition must contain 300 rows")
        for slot in OPTIONAL_SLOT_NAMES:
            present = counts[f"{slot}_present_rows"]
            absent = counts[f"{slot}_absent_rows"]
            if present + absent != 300:
                raise StageBProtocolError(f"{slot} optional-slot partition must sum to 300")
        for name, minimum in OPTIONAL_SLOT_MINIMUMS.items():
            if counts[name] < minimum:
                raise StageBProtocolError("held-out optional-slot coverage is below its minimum")
    return counts


def required_pass_count(actual_denominator: int) -> int:
    """Return the frozen integer numerator for a >=95% gate."""

    if isinstance(actual_denominator, bool) or not isinstance(actual_denominator, int):
        raise StageBProtocolError("actual denominator must be a positive integer")
    if actual_denominator <= 0:
        raise StageBProtocolError("actual denominator must be positive")
    return math.ceil(0.95 * actual_denominator)


def _language_gate_counts(records: Sequence[StageBRecord]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for language_tag in (StageBLanguageTag.ZH_HANT.value, StageBLanguageTag.MIXED.value):
        rows = [
            record
            for record in records
            if record.language_tag == language_tag
            and record.ai_scope == StageBAIScope.SUPPORTED.value
        ]
        result[language_tag] = {
            "supported_total": len(rows),
            "supported_play": sum(
                record.expected.intent == StageBIntent.SPOTIFY_PLAY_TRACK.value for record in rows
            ),
            "supported_unknown": sum(
                record.expected.intent == StageBIntent.UNKNOWN.value for record in rows
            ),
        }
    return result


def _validate_protocol_counts(records_by_split: Mapping[str, Sequence[StageBRecord]]) -> None:
    if set(records_by_split) != set(SPLIT_NAMES):
        raise StageBProtocolError("final protocol validation requires train, validation, and test splits")

    all_records = [record for records in records_by_split.values() for record in records]
    if len(all_records) != 3000:
        raise StageBProtocolError("final protocol corpus must contain exactly 3000 rows")

    for split in SPLIT_NAMES:
        counts = _class_counts(records_by_split[split])
        expected = EXPECTED_SPLIT_COUNTS[split]
        for key, expected_value in expected.items():
            actual = len(records_by_split[split]) if key == "total" else counts.get(key, 0)
            if actual != expected_value:
                raise StageBProtocolError("final protocol split counts do not match the frozen target")

    gates = _language_gate_counts(records_by_split[HELD_OUT_SPLIT])
    for gate in gates.values():
        if gate["supported_total"] < 100:
            raise StageBProtocolError("held-out language gate has fewer than 100 supported rows")
        if gate["supported_play"] < 40 or gate["supported_unknown"] < 40:
            raise StageBProtocolError("held-out language gate lacks its 40/40 class minima")

    optional_slot_partition(
        records_by_split[HELD_OUT_SPLIT],
        require_protocol_partition=True,
    )


def _build_manifest(records_by_split: Mapping[str, Sequence[StageBRecord]]) -> dict[str, Any]:
    all_records = [record for split in SPLIT_NAMES for record in records_by_split.get(split, ())]
    class_keys = ("supported_play", "supported_unknown", "deterministic_only", "safety_only")

    per_split_row_counts = {
        split: len(records_by_split.get(split, ())) for split in SPLIT_NAMES
    }
    per_split_class_counts: dict[str, dict[str, int]] = {}
    per_split_language_tag_counts: dict[str, dict[str, int]] = {}
    per_split_language_slice_counts: dict[str, dict[str, int]] = {}
    per_split_optional_counts: dict[str, dict[str, int]] = {}
    for split in SPLIT_NAMES:
        records = records_by_split.get(split, ())
        class_counts = _class_counts(records)
        per_split_class_counts[split] = {
            key: class_counts.get(key, 0) for key in class_keys
        }
        tags = Counter(record.language_tag for record in records)
        slices = Counter(record.language_slice for record in records)
        per_split_language_tag_counts[split] = {
            member.value: tags.get(member.value, 0) for member in StageBLanguageTag
        }
        per_split_language_slice_counts[split] = {
            member.value: slices.get(member.value, 0) for member in StageBLanguageSlice
        }
        per_split_optional_counts[split] = optional_slot_partition(records)

    scope_counts = Counter(record.ai_scope for record in all_records)
    intent_counts = Counter(record.expected.intent for record in all_records)
    language_tag_counts = Counter(record.language_tag for record in all_records)
    language_slice_counts = Counter(record.language_slice for record in all_records)
    optional_counts = optional_slot_partition(all_records)

    split_sha256 = {
        split: _sha256_json(_canonical_records(records_by_split.get(split, ())))
        for split in SPLIT_NAMES
    }
    corpus_payload = [
        {"split": split, "record": record.to_dict()}
        for split in SPLIT_NAMES
        for record in sorted(records_by_split.get(split, ()), key=_canonical_record_sort_key)
    ]
    corpus_sha256 = _sha256_json(corpus_payload)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "total_row_count": len(all_records),
        "per_split_row_counts": per_split_row_counts,
        "per_split_class_counts": per_split_class_counts,
        "per_split_language_tag_counts": per_split_language_tag_counts,
        "per_split_language_slice_counts": per_split_language_slice_counts,
        "per_split_optional_slot_counts": per_split_optional_counts,
        "ai_scope_counts": {
            member.value: scope_counts.get(member.value, 0) for member in StageBAIScope
        },
        "intent_counts": {
            member.value: intent_counts.get(member.value, 0) for member in StageBIntent
        },
        "language_tag_counts": {
            member.value: language_tag_counts.get(member.value, 0) for member in StageBLanguageTag
        },
        "language_slice_counts": {
            member.value: language_slice_counts.get(member.value, 0)
            for member in StageBLanguageSlice
        },
        "supported_play_count": optional_counts["supported_play_rows"],
        "supported_semantic_unknown_count": sum(
            record.ai_scope == StageBAIScope.SUPPORTED.value
            and record.expected.intent == StageBIntent.UNKNOWN.value
            for record in all_records
        ),
        "deterministic_only_count": scope_counts.get(StageBAIScope.DETERMINISTIC_ONLY.value, 0),
        "safety_only_count": scope_counts.get(StageBAIScope.SAFETY_ONLY.value, 0),
        "artist_present_count": optional_counts["artist_present_rows"],
        "artist_absent_count": optional_counts["artist_absent_rows"],
        "album_present_count": optional_counts["album_present_rows"],
        "album_absent_count": optional_counts["album_absent_rows"],
        "optional_slot_partition": optional_counts,
        "held_out_language_gates": _language_gate_counts(
            records_by_split.get(HELD_OUT_SPLIT, ())
        ),
        "source_group_count": len({record.source_group_id for record in all_records}),
        "split_sha256": split_sha256,
        "corpus_sha256": corpus_sha256,
        "canonicalization": "NFKC+casefold+punctuation-to-space+whitespace-collapse",
        "traditional_simplified_canonicalization": "not_implemented",
    }
    manifest["manifest_sha256"] = _sha256_json(manifest)
    return manifest


@dataclass(frozen=True, slots=True)
class StageBValidationResult:
    records_by_split: Mapping[str, tuple[StageBRecord, ...]]
    manifest: Mapping[str, Any]
    protocol_counts_enforced: bool

    def manifest_dict(self) -> dict[str, Any]:
        return json.loads(canonical_json(self.manifest))

    def manifest_json(self) -> str:
        return canonical_json(self.manifest)


def validate_corpus(
    splits: Mapping[str, Sequence[StageBRecord | Mapping[str, Any]]],
    *,
    enforce_protocol_counts: bool = False,
    stage_a_path: Path | None = DEFAULT_STAGE_A_CORPUS_PATH,
    verify_stage_a_identity: bool | None = None,
) -> StageBValidationResult:
    """Validate records and return deterministic evidence.

    ``enforce_protocol_counts=False`` is the compact synthetic-fixture mode.
    ``validate_protocol_corpus`` enables the exact 3,000-row final protocol.
    Passing ``stage_a_path=None`` disables only the Stage A utterance leakage
    comparison for an explicitly isolated schema test.
    """

    records_by_split = _coerce_splits(splits)
    stage_a_utterances = None
    if stage_a_path is not None:
        stage_a_utterances = load_stage_a_utterances(
            stage_a_path,
            verify_frozen_identity=verify_stage_a_identity,
        )
    _validate_cross_split_boundaries(
        records_by_split,
        stage_a_utterances=stage_a_utterances,
    )
    if enforce_protocol_counts:
        _validate_protocol_counts(records_by_split)
    manifest = _build_manifest(records_by_split)
    return StageBValidationResult(
        records_by_split=records_by_split,
        manifest=manifest,
        protocol_counts_enforced=enforce_protocol_counts,
    )


def validate_protocol_corpus(
    splits: Mapping[str, Sequence[StageBRecord | Mapping[str, Any]]],
    *,
    stage_a_path: Path | None = DEFAULT_STAGE_A_CORPUS_PATH,
    verify_stage_a_identity: bool | None = None,
) -> StageBValidationResult:
    """Validate the exact frozen 3,000-row Stage B protocol."""

    return validate_corpus(
        splits,
        enforce_protocol_counts=True,
        stage_a_path=stage_a_path,
        verify_stage_a_identity=verify_stage_a_identity,
    )


def load_split_records(path: Path) -> tuple[StageBRecord, ...]:
    """Load one explicit local JSON array without executing any external code."""

    return tuple(StageBRecord.from_mapping(row) for row in _read_json_array(Path(path)))


def validate_corpus_paths(
    split_paths: Mapping[str, Path],
    *,
    enforce_protocol_counts: bool = False,
    stage_a_path: Path | None = DEFAULT_STAGE_A_CORPUS_PATH,
    verify_stage_a_identity: bool | None = None,
) -> StageBValidationResult:
    """Load explicit local split files and validate them offline."""

    splits = {name: load_split_records(Path(path)) for name, path in split_paths.items()}
    return validate_corpus(
        splits,
        enforce_protocol_counts=enforce_protocol_counts,
        stage_a_path=stage_a_path,
        verify_stage_a_identity=verify_stage_a_identity,
    )


@dataclass(frozen=True, slots=True)
class NearDuplicateConfig:
    """Explicit placeholder until a corpus-build review freezes an algorithm."""

    algorithm: str = "unconfigured"
    ngram_size: int | None = None
    similarity_threshold: float | None = None
    hash_bits: int | None = None


@dataclass(frozen=True, slots=True)
class NearDuplicateResult:
    implemented: bool
    pairs: tuple[tuple[str, str], ...]
    reason: str


DEFAULT_NEAR_DUPLICATE_CONFIG = NearDuplicateConfig()


def inspect_near_duplicates(
    records: Sequence[StageBRecord],
    *,
    config: NearDuplicateConfig = DEFAULT_NEAR_DUPLICATE_CONFIG,
) -> NearDuplicateResult:
    """Expose the future near-duplicate seam without inventing a threshold."""

    del records, config
    return NearDuplicateResult(
        implemented=False,
        pairs=(),
        reason="near-duplicate algorithm/configuration remains a future corpus-build requirement",
    )


# Convenient aliases for callers that prefer shorter names while keeping the
# explicit Stage B names available in reports and tests.
Span = StageBSpan
Expected = StageBExpected
Record = StageBRecord
