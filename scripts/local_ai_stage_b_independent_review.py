"""Prepare deterministic packets for independent review of Stage B candidates.

This module is deliberately downstream of the frozen candidate artifacts. It
does not generate, relabel, rewrite, accept, reject, split, or train on a
candidate. It writes review allocations separately from validated raw external
decisions and their deterministic post-review aggregates.

The source identity is fail-closed against the frozen v6 artifact hashes.
A regenerated candidate corpus cannot silently reuse an old decision ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import local_ai_stage_b_corpus as protocol


REVIEW_WORKFLOW_VERSION = "stage-b-independent-review-v2"
REVIEW_STATUS = "pending_independent_review"
PACKET_COUNT = 12
ROWS_PER_PACKET = 300
EXPECTED_CANDIDATE_COUNT = PACKET_COUNT * ROWS_PER_PACKET
DEFAULT_STAGE_B_ARTIFACT_DIR = _REPO_ROOT / "artifacts" / "local_ai" / "stage_b" / "v6"
DEFAULT_REVIEW_DIR = DEFAULT_STAGE_B_ARTIFACT_DIR / "review"
ZH_HANS_SCRIPT_INVENTORY_PATH = _REPO_ROOT / "scripts" / "data" / "stage_b_zh_hans_script_inventory_v2.json"
ZH_HANS_SCRIPT_INVENTORY_SHA256 = "733a18812f93dd23ff3a5811ad8626d6b0aa663ba64f244f885ff3d3b037d7d8"

# These are the frozen v6 source identities.  They are intentionally
# literal and independent of the current candidate manifest.  The manifest is
# also recomputed and compared so a stale or hand-edited manifest cannot bless
# a different source corpus.
REVIEWED_SOURCE_IDENTITIES = MappingProxyType(
    {
        "candidate_corpus_sha256": (
            "fec537e73e45b4af68ad15bb9e75e09c0f3c2780fcf179a4dd8a3f0dc37a6238"
        ),
        "entity_catalog_sha256": (
            "7b0a09825cb40e046a7c27cc4f51f08aa22d42e5a5587c23710f831c3c0f15cb"
        ),
        "generator_config_sha256": (
            "132398500823674d3fec24361139145247f92b13a17cd7476e40110d4ac7df2e"
        ),
        "candidate_manifest_sha256": (
            "83e27d68f13821839278957b8bc5291ef18091ed135319670da5fd139612bea6"
        ),
    }
)

CANDIDATE_SOURCE_FIELDS = frozenset(
    {
        "candidate_id",
        "source_group_id",
        "utterance",
        "language_tag",
        "language_slice",
        "provisional_ai_scope",
        "provisional_expected",
        "provisional_optional_slot_status",
        "provisional_negative_reason",
        "template_family",
        "generation_source",
        "generator_version",
        "review_status",
    }
)
PACKET_FIELDS = (
    "candidate_id",
    "source_group_id",
    "utterance",
    "language_tag",
    "language_slice",
    "provisional_ai_scope",
    "provisional_expected",
    "provisional_optional_slot_status",
    "provisional_negative_reason",
    "template_family",
    "generator_version",
    "record_sha256",
)
PACKET_FIELD_SET = frozenset(PACKET_FIELDS)

DECISION_REQUIRED_FIELDS = frozenset(
    {"candidate_id", "record_sha256", "reviewer_role_id", "decision", "reason_codes"}
)
DECISION_OPTIONAL_FIELDS = frozenset({"reviewer_note"})
DECISION_FIELDS = DECISION_REQUIRED_FIELDS | DECISION_OPTIONAL_FIELDS
DECISION_VALUES = ("accept", "reject", "needs_correction")
CANDIDATE_AGGREGATE_STATES = (
    "pending",
    "accepted",
    "rejected",
    "needs_correction",
    "conflict",
)
POSITIVE_REASON_CODES = (
    "label_correct",
    "natural_language_ok",
    "span_correct",
    "scope_correct",
    "entity_surface_ok",
)
NEGATIVE_REASON_CODES = (
    "unnatural_language",
    "wrong_intent",
    "wrong_scope",
    "wrong_negative_reason",
    "wrong_track_span",
    "wrong_artist_span",
    "wrong_album_span",
    "wrong_optional_slot_status",
    "implausible_asr",
    "language_tag_mismatch",
    "traditional_simplified_mismatch",
    "entity_surface_artifact",
    "duplicate_semantics",
    "safety_boundary_problem",
    "other_review_blocker",
)
REASON_CODES = POSITIVE_REASON_CODES + NEGATIVE_REASON_CODES
REASON_CODE_SET = frozenset(REASON_CODES)
POSITIVE_REASON_CODE_SET = frozenset(POSITIVE_REASON_CODES)
NEGATIVE_REASON_CODE_SET = frozenset(NEGATIVE_REASON_CODES)
REVIEWER_ROLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RECORD_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
DECISION_PACKAGE_VERSION = "stage-b-independent-decision-package-v1"
REVIEW_PROGRESS_VERSION = "stage-b-review-progress-v1"
REVIEWED_V6_GIT_HEAD = "d3b71f9f02871f64191c924621f35f9bc4b2f9a4"
V6_MERGED_MAIN_BASELINE = "8790491de6da591330b5e8d29749f43754d2260a"
EXTERNAL_REVIEW_REPORT_NAME = "GEMINI_3_8_HIGH_STAGE_B_V6_REVIEW_REPORT.md"
MAX_DECISION_PACKET_BYTES = 5 * 1024 * 1024


class ReviewWorkflowError(ValueError):
    """Base class for deterministic review workflow failures."""


class ReviewSourceIdentityError(ReviewWorkflowError):
    """The source artifacts do not match the reviewed candidate corpus."""


class ReviewPacketError(ReviewWorkflowError):
    """The packet assignment or packet artifact is invalid."""


class ReviewDecisionError(ReviewWorkflowError):
    """A reviewer decision violates the closed submission schema."""


class ReviewDecisionPackageError(ReviewWorkflowError):
    """A complete external decision package fails closed validation."""


@dataclass(frozen=True, slots=True)
class ReviewSource:
    artifact_dir: Path
    identities: Mapping[str, str]
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, Any], ...]
    rows_by_id: Mapping[str, Mapping[str, Any]]
    entities_by_key: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class _PreparedCandidate:
    row: Mapping[str, Any]
    record_sha256: str
    scope: str
    language_tag: str
    slot_mode: str
    morphology_profile: str
    stratum: tuple[str, ...]


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_compatible(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        + b"\n"
    )


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_bytes(
        b"".join(
            _canonical_json(row).encode("utf-8") + b"\n"
            for row in rows
        )
    )


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewWorkflowError(f"cannot read JSON artifact: {path.name}") from exc
    if not isinstance(value, Mapping):
        raise ReviewWorkflowError(f"JSON artifact must be an object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[Mapping[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ReviewWorkflowError(f"cannot read JSONL artifact: {path.name}") from exc
    values: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReviewWorkflowError(
                f"invalid JSONL at {path.name}:{line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            raise ReviewWorkflowError(
                f"JSONL row must be an object at {path.name}:{line_number}"
            )
        values.append(value)
    return values


def _hash_without_field(payload: Mapping[str, Any], field: str) -> str:
    if field not in payload:
        raise ReviewSourceIdentityError(f"artifact is missing {field}")
    unsigned = dict(payload)
    del unsigned[field]
    return _sha256_json(unsigned)


def _require_hash(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or RECORD_HASH_RE.fullmatch(value) is None:
        raise ReviewSourceIdentityError(f"{field} is not a lowercase SHA-256")
    return value


def _validate_source_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload) != CANDIDATE_SOURCE_FIELDS:
        raise ReviewSourceIdentityError("candidate row fields are not closed")
    try:
        protocol._scan_forbidden_fields(payload)
        protocol._scan_sensitive_values(payload)
        protocol.StageBRecord.from_mapping(
            {
                "case_id": payload["candidate_id"],
                "source_group_id": payload["source_group_id"],
                "utterance": payload["utterance"],
                "language_tag": payload["language_tag"],
                "language_slice": payload["language_slice"],
                "ai_scope": payload["provisional_ai_scope"],
                "expected": payload["provisional_expected"],
                "optional_slot_status": payload["provisional_optional_slot_status"],
                "negative_reason": payload["provisional_negative_reason"],
                "template_family": payload["template_family"],
                "generator_version": payload["generator_version"],
            }
        )
    except (KeyError, protocol.StageBCorpusError) as exc:
        raise ReviewSourceIdentityError("candidate row failed source-schema validation") from exc
    if payload["review_status"] != REVIEW_STATUS:
        raise ReviewSourceIdentityError("candidate row is not pending independent review")
    if payload["generator_version"] != "stage-b-candidate-generator-v6":
        raise ReviewSourceIdentityError("candidate row generator version is not v6")
    if not isinstance(payload["generation_source"], str) or not payload["generation_source"]:
        raise ReviewSourceIdentityError("candidate row generation_source is invalid")
    return dict(payload)


def _source_group_number(source_group_id: str) -> str:
    try:
        prefix, number = source_group_id.rsplit("-", 1)
    except ValueError as exc:
        raise ReviewSourceIdentityError("source_group_id is not in the frozen format") from exc
    if prefix != "source-group" or not number.isdigit():
        raise ReviewSourceIdentityError("source_group_id is not in the frozen format")
    return number


def load_review_source(
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> ReviewSource:
    """Load and fail-closed validate the frozen v6 source artifacts."""

    safe_dir = protocol.validate_local_path(artifacts_dir, field="artifacts_dir")
    manifest = _read_json(safe_dir / "candidate_manifest.json")
    manifest_sha256 = _hash_without_field(manifest, "manifest_sha256")
    stored_manifest_sha256 = _require_hash(
        manifest.get("manifest_sha256"), field="manifest_sha256"
    )
    if manifest_sha256 != stored_manifest_sha256:
        raise ReviewSourceIdentityError("candidate manifest self-hash does not verify")

    catalog = _read_json(safe_dir / "entity_catalog.json")
    catalog_sha256 = _hash_without_field(catalog, "catalog_sha256")
    if catalog_sha256 != _require_hash(catalog.get("catalog_sha256"), field="catalog_sha256"):
        raise ReviewSourceIdentityError("entity catalog self-hash does not verify")
    entities = catalog.get("entities")
    if not isinstance(entities, list):
        raise ReviewSourceIdentityError("entity catalog entities must be a list")
    entity_by_key: dict[str, Mapping[str, str]] = {}
    for entity in entities:
        if not isinstance(entity, Mapping):
            raise ReviewSourceIdentityError("entity catalog contains a non-object")
        if set(entity) != {"entity_key", "language_tag", "artist", "track", "album"}:
            raise ReviewSourceIdentityError("entity catalog fields are not closed")
        key = entity.get("entity_key")
        if not isinstance(key, str) or key in entity_by_key:
            raise ReviewSourceIdentityError("entity catalog keys are not unique")
        entity_by_key[key] = dict(entity)

    generator_config = _read_json(safe_dir / "generator_config.json")
    generator_config_sha256 = _hash_without_field(
        generator_config, "generator_config_sha256"
    )
    if generator_config_sha256 != _require_hash(
        generator_config.get("generator_config_sha256"),
        field="generator_config_sha256",
    ):
        raise ReviewSourceIdentityError("generator config self-hash does not verify")
    script_inventory = _read_json(ZH_HANS_SCRIPT_INVENTORY_PATH)
    if (
        _hash_without_field(script_inventory, "inventory_sha256")
        != ZH_HANS_SCRIPT_INVENTORY_SHA256
        or script_inventory.get("inventory_sha256") != ZH_HANS_SCRIPT_INVENTORY_SHA256
        or generator_config.get("zh_hans_script_inventory_sha256")
        != ZH_HANS_SCRIPT_INVENTORY_SHA256
        or manifest.get("zh_hans_script_inventory_sha256")
        != ZH_HANS_SCRIPT_INVENTORY_SHA256
    ):
        raise ReviewSourceIdentityError("zh-Hans script inventory identity mismatch")

    raw_rows = _read_jsonl(safe_dir / "candidate_corpus.jsonl")
    rows = [_validate_source_row(row) for row in raw_rows]
    rows_by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        candidate_id = row["candidate_id"]
        if not isinstance(candidate_id, str) or candidate_id in rows_by_id:
            raise ReviewSourceIdentityError("candidate IDs are not unique")
        rows_by_id[candidate_id] = row
    if len(rows) != EXPECTED_CANDIDATE_COUNT:
        raise ReviewSourceIdentityError("candidate corpus row count is not 3,600")
    if _sha256_json(sorted(rows, key=lambda row: row["candidate_id"])) != manifest.get(
        "candidate_corpus_sha256"
    ):
        raise ReviewSourceIdentityError("candidate corpus hash does not match its manifest")

    queue = _read_jsonl(safe_dir / "candidate_review_queue.jsonl")
    queue_hash = _sha256_json(queue)
    if queue_hash != manifest.get("review_queue_sha256"):
        raise ReviewSourceIdentityError("review queue hash does not match its manifest")
    queue_by_id: dict[str, Mapping[str, Any]] = {}
    for entry in queue:
        if set(entry) != {"candidate_id", "record_sha256", "review_status", "review_reason"}:
            raise ReviewSourceIdentityError("candidate review queue fields are not closed")
        candidate_id = entry["candidate_id"]
        if not isinstance(candidate_id, str) or candidate_id in queue_by_id:
            raise ReviewSourceIdentityError("candidate review queue IDs are not unique")
        queue_by_id[candidate_id] = entry
        if entry["review_status"] != REVIEW_STATUS or entry["review_reason"] is not None:
            raise ReviewSourceIdentityError("candidate review queue is not empty/pending")
        if entry["record_sha256"] != _sha256_json(rows_by_id.get(candidate_id, {})):
            raise ReviewSourceIdentityError("candidate review queue record hash mismatch")
    if set(queue_by_id) != set(rows_by_id):
        raise ReviewSourceIdentityError("candidate review queue does not cover all rows")

    actual_identities = {
        "candidate_corpus_sha256": _sha256_json(
            sorted(rows, key=lambda row: row["candidate_id"])
        ),
        "entity_catalog_sha256": catalog_sha256,
        "generator_config_sha256": generator_config_sha256,
        "candidate_manifest_sha256": manifest_sha256,
    }
    if actual_identities != dict(REVIEWED_SOURCE_IDENTITIES):
        raise ReviewSourceIdentityError(
            "source artifacts do not match the frozen v6 identities"
        )
    for field, expected in dict(REVIEWED_SOURCE_IDENTITIES).items():
        manifest_field = "manifest_sha256" if field == "candidate_manifest_sha256" else field
        if manifest.get(manifest_field) != expected:
            raise ReviewSourceIdentityError(f"manifest identity mismatch: {field}")

    if manifest.get("total_row_count") != EXPECTED_CANDIDATE_COUNT:
        raise ReviewSourceIdentityError("manifest total_row_count is not 3,600")
    if manifest.get("source_group_count") != 600:
        raise ReviewSourceIdentityError("manifest source_group_count is not 600")
    if manifest.get("candidate_pool_split_status") != "unsplit":
        raise ReviewSourceIdentityError("candidate pool is not unsplit")
    if any(
        manifest.get(flag) is not False
        for flag in (
            "final_split_assigned",
            "held_out_sealed",
            "FINAL_STAGE_B_CORPUS",
            "training_authorized",
            "model_compute_authorized",
            "semantic_memory_enabled",
            "local_ai_fallback_approved",
        )
    ):
        raise ReviewSourceIdentityError("candidate manifest crosses the review boundary")

    group_counts = Counter(row["source_group_id"] for row in rows)
    if len(group_counts) != 600 or set(group_counts.values()) != {6}:
        raise ReviewSourceIdentityError("candidate source groups are not six-row groups")
    return ReviewSource(
        artifact_dir=safe_dir,
        identities=MappingProxyType(actual_identities),
        manifest=MappingProxyType(dict(manifest)),
        rows=tuple(MappingProxyType(row) for row in rows),
        rows_by_id=MappingProxyType(
            {candidate_id: MappingProxyType(dict(row)) for candidate_id, row in rows_by_id.items()}
        ),
        entities_by_key=MappingProxyType(
            {key: MappingProxyType(dict(entity)) for key, entity in entity_by_key.items()}
        ),
    )


def _review_scope(row: Mapping[str, Any]) -> str:
    if row["provisional_ai_scope"] != "supported":
        return str(row["provisional_ai_scope"])
    expected = row["provisional_expected"]
    if not isinstance(expected, Mapping):
        raise ReviewPacketError("candidate expected payload is not an object")
    return "supported_play" if expected["intent"] == "spotify_play_track" else "supported_unknown"


def _slot_mode(row: Mapping[str, Any]) -> str:
    if _review_scope(row) != "supported_play":
        return "not_applicable"
    status = row["provisional_optional_slot_status"]
    if not isinstance(status, Mapping):
        raise ReviewPacketError("supported play row is missing optional slot status")
    artist = status.get("artist") == "present"
    album = status.get("album") == "present"
    if artist and album:
        return "both"
    if artist:
        return "artist_only"
    if album:
        return "album_only"
    return "neither"


def _length_bucket(value: str, language_tag: str) -> str:
    units = len(value.replace(" ", "")) if language_tag.startswith("zh-") else len(value.split())
    if units <= 3:
        return "1-3"
    if units <= 6:
        return "4-6"
    return "7+"


def _surface_features(values: Sequence[str]) -> str:
    joined = " ".join(values)
    features: list[str] = []
    if any(character.isdigit() for character in joined):
        features.append("digit")
    if any(unicodedata.category(character).startswith("P") for character in joined):
        features.append("punctuation")
    return "+".join(features) if features else "plain"


def _morphology_profile(entity: Mapping[str, str]) -> str:
    language_tag = entity["language_tag"]
    artist = entity["artist"]
    if language_tag == "zh-Hant":
        artist_profile = "band_suffix" if artist.endswith("樂團") else "non_suffix"
    elif language_tag == "zh-Hans":
        artist_profile = "band_suffix" if artist.endswith("乐团") else "non_suffix"
    else:
        artist_profile = _length_bucket(artist, language_tag)
    return ";".join(
        (
            f"artist={artist_profile}",
            f"track={_length_bucket(entity['track'], language_tag)}",
            f"album={_length_bucket(entity['album'], language_tag)}",
            f"surface={_surface_features((artist, entity['track'], entity['album']))}",
        )
    )


def _prepared_candidates(source: ReviewSource) -> tuple[_PreparedCandidate, ...]:
    prepared: list[_PreparedCandidate] = []
    for row in sorted(source.rows, key=lambda item: item["candidate_id"]):
        group_number = _source_group_number(str(row["source_group_id"]))
        entity_key = f"synthetic-entity-{group_number}"
        entity = source.entities_by_key.get(entity_key)
        if entity is None:
            raise ReviewPacketError("candidate source group has no catalog entity")
        scope = _review_scope(row)
        slot_mode = _slot_mode(row)
        morphology = _morphology_profile(entity)
        prepared.append(
            _PreparedCandidate(
                row=row,
                record_sha256=_sha256_json(row),
                scope=scope,
                language_tag=str(row["language_tag"]),
                slot_mode=slot_mode,
                morphology_profile=morphology,
                stratum=(
                    scope,
                    str(row["language_tag"]),
                    str(row["template_family"]),
                    slot_mode,
                    morphology,
                ),
            )
        )
    return tuple(prepared)


def _packet_payload(item: _PreparedCandidate) -> dict[str, Any]:
    row = item.row
    payload = {
        field: json.loads(_canonical_json(row[field]))
        for field in PACKET_FIELDS
        if field != "record_sha256"
    }
    payload["record_sha256"] = item.record_sha256
    if set(payload) != PACKET_FIELD_SET:
        raise ReviewPacketError("packet row fields are not closed")
    return payload


def _packet_assignments(
    source: ReviewSource,
) -> tuple[dict[str, list[dict[str, Any]]], tuple[_PreparedCandidate, ...]]:
    prepared = _prepared_candidates(source)
    buckets: dict[tuple[str, ...], list[_PreparedCandidate]] = defaultdict(list)
    for item in prepared:
        buckets[item.stratum].append(item)
    for bucket in buckets.values():
        bucket.sort(key=lambda item: item.row["candidate_id"])

    ordered: list[_PreparedCandidate] = []
    for offset in range(max(len(bucket) for bucket in buckets.values())):
        for stratum in sorted(buckets):
            bucket = buckets[stratum]
            if offset < len(bucket):
                ordered.append(bucket[offset])
    if len(ordered) != EXPECTED_CANDIDATE_COUNT:
        raise ReviewPacketError("stratified assignment lost candidate rows")

    packets = {
        f"packet-{packet_number:02d}": []
        for packet_number in range(1, PACKET_COUNT + 1)
    }
    for ordinal, item in enumerate(ordered):
        packet_id = f"packet-{ordinal % PACKET_COUNT + 1:02d}"
        packets[packet_id].append(_packet_payload(item))
    if any(len(rows) != ROWS_PER_PACKET for rows in packets.values()):
        raise ReviewPacketError("deterministic packet assignment is not 300 rows each")
    seen = [row["candidate_id"] for rows in packets.values() for row in rows]
    if len(seen) != len(set(seen)) or set(seen) != set(source.rows_by_id):
        raise ReviewPacketError("packet assignment is not an exact once-only coverage")
    return packets, prepared


def _counts(values: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _packet_diversity(
    packet_rows: Sequence[Mapping[str, Any]],
    prepared_by_id: Mapping[str, _PreparedCandidate],
) -> dict[str, Any]:
    items = [prepared_by_id[row["candidate_id"]] for row in packet_rows]
    return {
        "scope_counts": _counts([item.scope for item in items]),
        "language_counts": _counts([item.language_tag for item in items]),
        "template_family_counts": _counts(
            [str(item.row["template_family"]) for item in items]
        ),
        "slot_mode_counts": _counts([item.slot_mode for item in items]),
        "morphology_profile_counts": _counts(
            [item.morphology_profile for item in items]
        ),
    }


def _decision_schema_payload() -> dict[str, Any]:
    return {
        "format": "JSONL; one decision object per line",
        "required_fields": sorted(DECISION_REQUIRED_FIELDS),
        "optional_fields": sorted(DECISION_OPTIONAL_FIELDS),
        "decision_values": list(DECISION_VALUES),
        "reason_codes": list(REASON_CODES),
        "accept_requires_all": list(POSITIVE_REASON_CODES),
        "reject_or_needs_correction_requires_any": list(NEGATIVE_REASON_CODES),
        "reviewer_role_id_pattern": REVIEWER_ROLE_RE.pattern,
        "pending_decisions_allowed": False,
        "candidate_aggregate_states": list(CANDIDATE_AGGREGATE_STATES),
        "conflict_resolution": {"automatic": False},
    }


def _review_manifest(
    source: ReviewSource,
    packets: Mapping[str, Sequence[Mapping[str, Any]]],
    prepared: Sequence[_PreparedCandidate],
) -> dict[str, Any]:
    prepared_by_id = {item.row["candidate_id"]: item for item in prepared}
    packet_hashes = {
        packet_id: _sha256_json(list(rows))
        for packet_id, rows in packets.items()
    }
    packet_diversity = {
        packet_id: _packet_diversity(rows, prepared_by_id)
        for packet_id, rows in packets.items()
    }
    base: dict[str, Any] = {
        "review_manifest_version": 2,
        "review_workflow_version": REVIEW_WORKFLOW_VERSION,
        "review_status": REVIEW_STATUS,
        "source_artifacts": {
            "candidate_corpus": "../candidate_corpus.jsonl",
            "entity_catalog": "../entity_catalog.json",
            "generator_config": "../generator_config.json",
            "candidate_manifest": "../candidate_manifest.json",
        },
        "source_identities": dict(REVIEWED_SOURCE_IDENTITIES),
        "packet_assignment": {
            "algorithm": "stratified_round_robin_v1",
            "packet_count": PACKET_COUNT,
            "rows_per_packet": ROWS_PER_PACKET,
            "packets_are_not_splits": True,
        },
        "packet_ids": list(packets),
        "packet_row_counts": {packet_id: len(rows) for packet_id, rows in packets.items()},
        "packet_hashes": packet_hashes,
        "packet_diversity": packet_diversity,
        "all_candidates_exactly_once": True,
        "decision_storage": {
            "directory": "decisions",
            "format": "JSONL",
            "decision_count": 0,
            "raw_decision_counts": {
                decision_value: 0 for decision_value in DECISION_VALUES
            },
            "reviewed": 0,
            "accepted": 0,
            "rejected": 0,
            "needs_correction": 0,
            "conflict": 0,
            "pending": EXPECTED_CANDIDATE_COUNT,
        },
        "decision_schema": _decision_schema_payload(),
        "candidate_aggregate_states": list(CANDIDATE_AGGREGATE_STATES),
        "conflict_resolution": {"automatic": False},
        "source_group_reporting": {
            "row_level_decisions": True,
            "auto_propagate_decisions": False,
            "fully_accepted_requires_each_row": True,
            "health_states": [
                "unreviewed",
                "partially_reviewed",
                "fully_accepted",
                "partially_rejected",
                "needs_correction",
                "review_conflict",
            ],
        },
        "final_split_assigned": False,
        "held_out_sealed": False,
        "training_authorized": False,
        "model_compute_authorized": False,
        "semantic_memory_enabled": False,
        "local_ai_fallback_approved": False,
        "stage_a_access": "forbidden",
        "network_access": False,
        "subprocess_access": False,
        "model_access": False,
    }
    base["review_manifest_sha256"] = _sha256_json(base)
    return base


def _decisions_readme(manifest: Mapping[str, Any]) -> str:
    return """# Independent review decisions

This directory starts empty: no independent reviewer decision has been
submitted. `review_manifest.json` records `decision_count=0`, `reviewed=0`,
`conflict=0`, and `pending=3600`. Raw reviewer submissions are preserved;
candidate progress is aggregated separately.

A future submission must be JSONL with one object per line and exactly these
required fields:

```json
{
  "candidate_id": "candidate-00001",
  "record_sha256": "<the hash from the matching packet row>",
  "reviewer_role_id": "independent-reviewer-a",
  "decision": "accept",
  "reason_codes": [
    "label_correct",
    "natural_language_ok",
    "span_correct",
    "scope_correct",
    "entity_surface_ok"
  ]
}
```

`reviewer_note` is optional. The only decisions are `accept`, `reject`, and
`needs_correction`; pending is not a submitted decision. An accept requires
all five positive reason codes. A reject or needs-correction decision requires
at least one negative reason code. The offline validator also binds every
decision to the frozen v6 source identities and rejects duplicate
decisions from the same reviewer for the same candidate.

Multiple reviewers may review the same candidate. For each candidate, the
aggregate state is `pending` when there is no submitted decision, the matching
state (`accepted`, `rejected`, or `needs_correction`) when all submitted
decisions have the same value, and `conflict` when submitted values disagree.
There is no majority vote, reviewer precedence, reject-wins rule, or automatic
adjudication. Raw decisions remain available in `decision_count` and
`raw_decision_counts`; aggregate progress counts each candidate once.

Do not add provider IDs, credentials, OAuth data, private paths, user IDs,
clarification tokens, production authority data, or split labels. Do not edit
the candidate corpus or silently rewrite a candidate. `needs_correction`
rows remain excluded from later selection until a separate reviewed correction
workflow exists.

`conflict` remains unresolved and is ineligible for any future final selection
until a separately reviewed adjudication workflow exists. This PR does not
implement adjudication, a final acceptance ledger, or a final 3,000-row
selector.

This is a human/external-reviewer input boundary. Passing unit tests or the
production-alignment gate is supporting evidence only and never creates an
accept decision.

To validate a local JSONL submission without writing a ledger:

```text
.venv\\Scripts\\python.exe scripts\\local_ai_stage_b_independent_review.py --validate-decisions <decisions.jsonl>
```

The validator is offline-only and fails closed if the candidate artifact
identity differs from the frozen v6 hashes in the review manifest.
"""


def build_review_artifacts(
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    *,
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Build packets and an empty decision boundary without changing source rows."""

    source = load_review_source(artifacts_dir)
    safe_review_dir = protocol.validate_local_path(review_dir, field="review_dir")
    decision_dir = safe_review_dir / "decisions"
    if decision_dir.exists():
        submitted = [
            path
            for path in decision_dir.iterdir()
            if path.is_file() and path.name != "README.md"
        ]
        if submitted:
            raise ReviewWorkflowError(
                "refusing to overwrite existing independent decision submissions"
            )
    safe_review_dir.mkdir(parents=True, exist_ok=True)
    (safe_review_dir / "packets").mkdir(parents=True, exist_ok=True)
    decision_dir.mkdir(parents=True, exist_ok=True)

    packets, prepared = _packet_assignments(source)
    manifest = _review_manifest(source, packets, prepared)
    for packet_id, rows in packets.items():
        _write_jsonl(safe_review_dir / "packets" / f"{packet_id}.jsonl", rows)
    _write_json(safe_review_dir / "review_manifest.json", manifest)
    (decision_dir / "README.md").write_bytes(_decisions_readme(manifest).encode("utf-8"))
    return {
        "review_dir": str(safe_review_dir),
        "manifest": manifest,
        "packet_hashes": manifest["packet_hashes"],
        "packet_row_counts": manifest["packet_row_counts"],
    }


def _validate_decision_against_source(
    decision: Mapping[str, Any],
    source: ReviewSource,
) -> dict[str, Any]:
    if not isinstance(decision, Mapping):
        raise ReviewDecisionError("decision must be an object")
    keys = set(decision)
    if not DECISION_REQUIRED_FIELDS <= keys or not keys <= DECISION_FIELDS:
        raise ReviewDecisionError("decision fields are not closed")
    candidate_id = decision.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ReviewDecisionError("candidate_id must be non-empty text")
    row = source.rows_by_id.get(candidate_id)
    if row is None:
        raise ReviewDecisionError("unknown candidate_id")
    record_sha256 = decision.get("record_sha256")
    if not isinstance(record_sha256, str) or RECORD_HASH_RE.fullmatch(record_sha256) is None:
        raise ReviewDecisionError("record_sha256 must be a lowercase SHA-256")
    expected_hash = _sha256_json(row)
    if record_sha256 != expected_hash:
        raise ReviewDecisionError("record_sha256 does not match the candidate row")
    reviewer_role_id = decision.get("reviewer_role_id")
    if (
        not isinstance(reviewer_role_id, str)
        or REVIEWER_ROLE_RE.fullmatch(reviewer_role_id) is None
    ):
        raise ReviewDecisionError("reviewer_role_id must be an opaque role identifier")
    decision_value = decision.get("decision")
    if decision_value not in DECISION_VALUES:
        raise ReviewDecisionError("decision is outside the closed enum")
    reason_codes = decision.get("reason_codes")
    if not isinstance(reason_codes, list) or not reason_codes:
        raise ReviewDecisionError("reason_codes must be a non-empty list")
    if len(reason_codes) > len(REASON_CODES) or any(
        not isinstance(code, str) or code not in REASON_CODE_SET for code in reason_codes
    ):
        raise ReviewDecisionError("reason_codes contains an unknown code")
    if len(set(reason_codes)) != len(reason_codes):
        raise ReviewDecisionError("reason_codes must not contain duplicates")
    reason_set = set(reason_codes)
    if decision_value == "accept":
        if not POSITIVE_REASON_CODE_SET <= reason_set:
            raise ReviewDecisionError("accept requires all explicit positive evidence codes")
        if reason_set & NEGATIVE_REASON_CODE_SET:
            raise ReviewDecisionError("accept cannot contain a negative blocker code")
    elif not reason_set & NEGATIVE_REASON_CODE_SET:
        raise ReviewDecisionError(
            "reject and needs_correction require at least one negative reason code"
        )
    if "reviewer_note" in decision:
        note = decision["reviewer_note"]
        if not isinstance(note, str) or len(note) > 2000:
            raise ReviewDecisionError("reviewer_note must be bounded text")
    normalized = dict(decision)
    normalized["reason_codes"] = list(reason_codes)
    return normalized


def _validate_decisions_against_source(
    decisions: Sequence[Mapping[str, Any]],
    source: ReviewSource,
) -> tuple[dict[str, Any], ...]:
    if isinstance(decisions, (str, bytes, Mapping)):
        raise ReviewDecisionError("decisions must be a sequence of decision objects")
    validated: list[dict[str, Any]] = []
    seen_reviewer_candidates: set[tuple[str, str]] = set()
    for decision in decisions:
        normalized = _validate_decision_against_source(decision, source)
        key = (normalized["reviewer_role_id"], normalized["candidate_id"])
        if key in seen_reviewer_candidates:
            raise ReviewDecisionError(
                "duplicate decision from the same reviewer for the same candidate"
            )
        seen_reviewer_candidates.add(key)
        validated.append(normalized)
    return tuple(validated)


def validate_decisions(
    decisions: Sequence[Mapping[str, Any]],
    *,
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> tuple[dict[str, Any], ...]:
    """Validate external decisions against the exact reviewed source identity."""

    return _validate_decisions_against_source(decisions, load_review_source(artifacts_dir))


def _packet_map(source: ReviewSource) -> Mapping[str, str]:
    packets, _prepared = _packet_assignments(source)
    return MappingProxyType(
        {
            row["candidate_id"]: packet_id
            for packet_id, rows in packets.items()
            for row in rows
        }
    )


def _candidate_aggregate_state(decision_values: Sequence[str]) -> str:
    if not decision_values:
        return "pending"
    if len(set(decision_values)) != 1:
        return "conflict"
    return {
        "accept": "accepted",
        "reject": "rejected",
        "needs_correction": "needs_correction",
    }[decision_values[0]]


def _candidate_aggregate_states(
    decisions: Sequence[Mapping[str, Any]],
    candidate_ids: Sequence[str],
) -> dict[str, str]:
    decisions_by_candidate: dict[str, list[str]] = defaultdict(list)
    for decision in decisions:
        decisions_by_candidate[decision["candidate_id"]].append(decision["decision"])
    return {
        candidate_id: _candidate_aggregate_state(decisions_by_candidate[candidate_id])
        for candidate_id in candidate_ids
    }


def _candidate_state_counts(candidate_states: Mapping[str, str]) -> dict[str, int]:
    counts = Counter(candidate_states.values())
    return {
        state: counts[state]
        for state in CANDIDATE_AGGREGATE_STATES
    }


def _raw_decision_counts(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts = Counter(decision["decision"] for decision in decisions)
    return {
        decision_value: counts[decision_value]
        for decision_value in DECISION_VALUES
    }


def _progress_dimension(
    decisions: Sequence[Mapping[str, Any]],
    key_for_candidate: Mapping[str, str],
    candidate_states: Mapping[str, str],
) -> dict[str, dict[str, int]]:
    raw_decision_counts: dict[str, Counter[str]] = defaultdict(Counter)
    candidate_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for decision in decisions:
        key = key_for_candidate[decision["candidate_id"]]
        raw_decision_counts[key][decision["decision"]] += 1
    for candidate_id, key in key_for_candidate.items():
        candidate_counts[key][candidate_states[candidate_id]] += 1
    keys = sorted(set(key_for_candidate.values()))
    for key in keys:
        candidate_count = sum(candidate_counts[key].values())
        reviewed_count = candidate_count - candidate_counts[key]["pending"]
        if (
            candidate_count != sum(candidate_counts[key][state] for state in CANDIDATE_AGGREGATE_STATES)
            or reviewed_count
            != sum(
                candidate_counts[key][state]
                for state in CANDIDATE_AGGREGATE_STATES
                if state != "pending"
            )
            or raw_decision_counts[key].total()
            != sum(raw_decision_counts[key][decision_value] for decision_value in DECISION_VALUES)
        ):
            raise ReviewWorkflowError(
                f"candidate aggregate dimension invariant failed for {key}"
            )
    return {
        key: {
            "candidate_count": sum(candidate_counts[key].values()),
            "decision_count": raw_decision_counts[key].total(),
            "raw_decision_counts": {
                decision_value: raw_decision_counts[key][decision_value]
                for decision_value in DECISION_VALUES
            },
            "reviewed_candidates": sum(
                candidate_counts[key][state]
                for state in CANDIDATE_AGGREGATE_STATES
                if state != "pending"
            ),
            "accepted": candidate_counts[key]["accepted"],
            "rejected": candidate_counts[key]["rejected"],
            "needs_correction": candidate_counts[key]["needs_correction"],
            "conflict": candidate_counts[key]["conflict"],
            "pending": candidate_counts[key]["pending"],
            "candidate_state_counts": {
                state: candidate_counts[key][state]
                for state in CANDIDATE_AGGREGATE_STATES
            },
        }
        for key in keys
    }


def _progress_by_reviewer_role(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    decision_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reviewed: dict[str, set[str]] = defaultdict(set)
    for decision in decisions:
        role = decision["reviewer_role_id"]
        decision_counts[role][decision["decision"]] += 1
        reviewed[role].add(decision["candidate_id"])
    return {
        role: {
            "decision_count": decision_counts[role].total(),
            "raw_decision_counts": {
                decision_value: decision_counts[role][decision_value]
                for decision_value in DECISION_VALUES
            },
            "reviewed_candidates": len(reviewed[role]),
        }
        for role in sorted(decision_counts)
    }


def review_progress(
    decisions: Sequence[Mapping[str, Any]],
    *,
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Return raw submission and unique candidate aggregate progress."""

    source = load_review_source(artifacts_dir)
    validated = _validate_decisions_against_source(decisions, source)
    packet_by_candidate = _packet_map(source)
    row_by_id = source.rows_by_id
    prepared_by_id = {
        item.row["candidate_id"]: item for item in _prepared_candidates(source)
    }
    candidate_states = _candidate_aggregate_states(
        validated,
        [str(row["candidate_id"]) for row in source.rows],
    )
    candidate_state_counts = _candidate_state_counts(candidate_states)
    raw_decision_counts = _raw_decision_counts(validated)
    total_candidates = len(source.rows)
    reviewed = total_candidates - candidate_state_counts["pending"]
    if (
        sum(candidate_state_counts.values()) != total_candidates
        or reviewed
        != (
            candidate_state_counts["accepted"]
            + candidate_state_counts["rejected"]
            + candidate_state_counts["needs_correction"]
            + candidate_state_counts["conflict"]
        )
    ):
        raise ReviewWorkflowError("candidate aggregate progress invariant failed")
    return {
        "total_candidates": total_candidates,
        "decision_count": len(validated),
        "raw_decision_counts": raw_decision_counts,
        "reviewed": reviewed,
        "accepted": candidate_state_counts["accepted"],
        "rejected": candidate_state_counts["rejected"],
        "needs_correction": candidate_state_counts["needs_correction"],
        "conflict": candidate_state_counts["conflict"],
        "pending": candidate_state_counts["pending"],
        "candidate_state_counts": candidate_state_counts,
        "by_packet": _progress_dimension(
            validated, packet_by_candidate, candidate_states
        ),
        "by_language": _progress_dimension(
            validated,
            {candidate_id: str(row["language_tag"]) for candidate_id, row in row_by_id.items()},
            candidate_states,
        ),
        "by_scope": _progress_dimension(
            validated,
            {candidate_id: item.scope for candidate_id, item in prepared_by_id.items()},
            candidate_states,
        ),
        "by_template_family": _progress_dimension(
            validated,
            {
                candidate_id: str(row["template_family"])
                for candidate_id, row in row_by_id.items()
            },
            candidate_states,
        ),
        "by_slot_mode": _progress_dimension(
            validated,
            {candidate_id: item.slot_mode for candidate_id, item in prepared_by_id.items()},
            candidate_states,
        ),
        "by_reviewer_role": _progress_by_reviewer_role(validated),
    }


def source_group_report(
    decisions: Sequence[Mapping[str, Any]],
    *,
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> dict[str, dict[str, Any]]:
    """Report group health from direct row decisions without propagation."""

    source = load_review_source(artifacts_dir)
    validated = _validate_decisions_against_source(decisions, source)
    by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    rows_by_group: dict[str, list[str]] = defaultdict(list)
    for row in source.rows:
        rows_by_group[str(row["source_group_id"])].append(str(row["candidate_id"]))
    for decision in validated:
        by_group[str(source.rows_by_id[decision["candidate_id"]]["source_group_id"])].append(
            decision
        )

    report: dict[str, dict[str, Any]] = {}
    for group_id in sorted(rows_by_group):
        candidate_ids = sorted(rows_by_group[group_id])
        group_decisions = by_group[group_id]
        candidate_states = _candidate_aggregate_states(group_decisions, candidate_ids)
        candidate_state_counts = _candidate_state_counts(candidate_states)
        decision_values = [
            decision["decision"] for decision in group_decisions
        ]
        if candidate_state_counts["conflict"]:
            health = "review_conflict"
        elif candidate_state_counts["needs_correction"]:
            health = "needs_correction"
        elif candidate_state_counts["rejected"]:
            health = "partially_rejected"
        elif all(
            candidate_states[candidate_id] == "accepted"
            for candidate_id in candidate_ids
        ):
            health = "fully_accepted"
        elif candidate_state_counts["pending"] == len(candidate_ids):
            health = "unreviewed"
        else:
            health = "partially_reviewed"
        reviewed_ids = sorted(
            candidate_id
            for candidate_id, state in candidate_states.items()
            if state != "pending"
        )
        report[group_id] = {
            "health": health,
            "candidate_count": len(candidate_ids),
            "reviewed_candidate_ids": reviewed_ids,
            "unreviewed_candidate_ids": [
                candidate_id
                for candidate_id in candidate_ids
                if candidate_states[candidate_id] == "pending"
            ],
            "direct_decision_count": len(group_decisions),
            "raw_decision_counts": dict(sorted(Counter(decision_values).items())),
            "candidate_states": candidate_states,
            "candidate_state_counts": candidate_state_counts,
        }
    return report


def _decision_jsonl_from_bytes(data: bytes, *, filename: str) -> list[Mapping[str, Any]]:
    """Parse exactly the bytes later preserved as raw reviewer evidence."""

    if len(data) > MAX_DECISION_PACKET_BYTES:
        raise ReviewDecisionPackageError(f"decision packet is too large: {filename}")
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ReviewDecisionPackageError(f"decision packet is not UTF-8: {filename}") from exc

    def unique_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ReviewDecisionPackageError(f"duplicate JSON key in {filename}")
            value[key] = item
        return value

    rows: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, object_pairs_hook=unique_object_keys)
        except json.JSONDecodeError as exc:
            raise ReviewDecisionPackageError(
                f"malformed decision JSONL at {filename}:{line_number}"
            ) from exc
        if not isinstance(row, Mapping):
            raise ReviewDecisionPackageError(
                f"decision JSONL row is not an object at {filename}:{line_number}"
            )
        rows.append(row)
    return rows


def _deterministic_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def package_independent_decisions(
    source_dir: str | Path,
    *,
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
) -> dict[str, Any]:
    """Validate and preserve one exact-once, 12-packet external review set.

    Every input and every existing output is checked before a missing file is
    created. Identical reruns are allowed; conflicting raw or derived bytes
    are never overwritten. The initial review manifest is read, not modified.
    """

    source = load_review_source(artifacts_dir)
    safe_source_dir = protocol.validate_local_path(source_dir, field="source_dir")
    safe_review_dir = protocol.validate_local_path(review_dir, field="review_dir")
    if not safe_source_dir.is_dir() or not safe_review_dir.is_dir():
        raise ReviewDecisionPackageError("source or frozen review directory is missing")
    if safe_review_dir.resolve() != (source.artifact_dir / "review").resolve():
        raise ReviewDecisionPackageError("review target is not the source's frozen review directory")

    packets, prepared = _packet_assignments(source)
    expected_initial_manifest = _review_manifest(source, packets, prepared)
    actual_initial_manifest = _read_json(safe_review_dir / "review_manifest.json")
    if dict(actual_initial_manifest) != expected_initial_manifest:
        raise ReviewDecisionPackageError("initial review manifest identity or state mismatch")
    for packet_id, packet_rows in packets.items():
        frozen_path = safe_review_dir / "packets" / f"{packet_id}.jsonl"
        if _read_jsonl(frozen_path) != packet_rows:
            raise ReviewDecisionPackageError(f"frozen source packet mismatch: {packet_id}")

    expected_filenames = {
        f"packet-{number:02d}.decisions.jsonl" for number in range(1, PACKET_COUNT + 1)
    }
    found_filenames = {path.name for path in safe_source_dir.iterdir() if path.suffix == ".jsonl"}
    if found_filenames != expected_filenames:
        raise ReviewDecisionPackageError("external decision packet file set mismatch")

    packet_by_candidate = _packet_map(source)
    raw_by_filename: dict[str, bytes] = {}
    file_entries: dict[str, dict[str, Any]] = {}
    all_decisions: list[Mapping[str, Any]] = []
    for number in range(1, PACKET_COUNT + 1):
        packet_id = f"packet-{number:02d}"
        filename = f"{packet_id}.decisions.jsonl"
        source_path = safe_source_dir / filename
        if not source_path.is_file():
            raise ReviewDecisionPackageError(f"missing decision packet: {filename}")
        raw = source_path.read_bytes()
        rows = _decision_jsonl_from_bytes(raw, filename=filename)
        if len(rows) != ROWS_PER_PACKET:
            raise ReviewDecisionPackageError(f"decision packet row count mismatch: {filename}")
        candidate_ids = [row.get("candidate_id") for row in rows]
        if any(not isinstance(candidate_id, str) for candidate_id in candidate_ids):
            raise ReviewDecisionPackageError(f"invalid decision candidate_id: {filename}")
        if len(set(candidate_ids)) != ROWS_PER_PACKET or {
            candidate_id for candidate_id, assigned in packet_by_candidate.items()
            if assigned == packet_id
        } != set(candidate_ids):
            raise ReviewDecisionPackageError(f"decision/source packet assignment mismatch: {filename}")
        raw_by_filename[filename] = raw
        digest = hashlib.sha256(raw).hexdigest()
        file_entries[packet_id] = {
            "filename": filename,
            "row_count": len(rows),
            "external_source_sha256": digest,
            "packaged_sha256": digest,
            "frozen_packet_canonical_sha256": expected_initial_manifest["packet_hashes"][packet_id],
        }
        all_decisions.extend(rows)

    validated = _validate_decisions_against_source(all_decisions, source)
    candidate_ids = [decision["candidate_id"] for decision in validated]
    duplicate_candidates = len(candidate_ids) - len(set(candidate_ids))
    if (
        len(validated) != EXPECTED_CANDIDATE_COUNT
        or duplicate_candidates
        or set(candidate_ids) != set(source.rows_by_id)
    ):
        raise ReviewDecisionPackageError("complete exact-once candidate coverage failed")

    progress = review_progress(validated, artifacts_dir=source.artifact_dir)
    report_path = safe_source_dir / EXTERNAL_REVIEW_REPORT_NAME
    report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest() if report_path.is_file() else None
    manifest: dict[str, Any] = {
        "decision_package_version": DECISION_PACKAGE_VERSION,
        "source_identities": dict(source.identities),
        "initial_review_manifest_sha256": expected_initial_manifest["review_manifest_sha256"],
        "reviewed_git_head": REVIEWED_V6_GIT_HEAD,
        "merged_main_baseline": V6_MERGED_MAIN_BASELINE,
        "reviewer_role_ids": sorted({decision["reviewer_role_id"] for decision in validated}),
        "packet_assignment": dict(expected_initial_manifest["packet_assignment"]),
        "packet_files": file_entries,
        "external_review_report": (
            {"logical_name": EXTERNAL_REVIEW_REPORT_NAME, "sha256": report_sha256}
            if report_sha256 is not None else None
        ),
        "decision_count": len(validated),
        "unique_candidate_count": len(set(candidate_ids)),
        "duplicate_candidate_count": duplicate_candidates,
        "coverage_exact": True,
        "raw_decision_counts": progress["raw_decision_counts"],
        "package_status": "complete_exact_once",
        "packets_are_not_splits": True,
        "final_selection_authorized": False,
        "final_split_assigned": False,
        "held_out_sealed": False,
        "training_authorized": False,
        "model_compute_authorized": False,
        "semantic_memory_enabled": False,
        "local_ai_fallback_approved": False,
    }
    manifest["decision_manifest_sha256"] = _sha256_json(manifest)
    progress_artifact: dict[str, Any] = {
        "review_progress_version": REVIEW_PROGRESS_VERSION,
        "source_identities": dict(source.identities),
        "decision_manifest_sha256": manifest["decision_manifest_sha256"],
        "packets_are_not_splits": True,
        "final_selection_authorized": False,
        "training_authorized": False,
        "model_compute_authorized": False,
        **progress,
    }
    progress_artifact["review_progress_sha256"] = _sha256_json(progress_artifact)

    decision_dir = safe_review_dir / "decisions"
    if decision_dir.is_symlink() or (decision_dir.exists() and not decision_dir.is_dir()):
        raise ReviewDecisionPackageError("decision target is not a directory")
    if decision_dir.exists():
        unexpected = {
            path.name for path in decision_dir.iterdir()
            if path.name not in expected_filenames | {"README.md"}
        }
        if unexpected:
            raise ReviewDecisionPackageError("unexpected existing decision submission")
    desired: dict[Path, bytes] = {
        decision_dir / filename: raw for filename, raw in raw_by_filename.items()
    }
    desired[safe_review_dir / "decision_manifest.json"] = _deterministic_json_bytes(manifest)
    desired[safe_review_dir / "review_progress.json"] = _deterministic_json_bytes(progress_artifact)
    for target, data in desired.items():
        if target.is_symlink() or (target.exists() and (not target.is_file() or target.read_bytes() != data)):
            raise ReviewDecisionPackageError(f"refusing to overwrite conflicting evidence: {target.name}")
    if any((safe_source_dir / name).read_bytes() != raw for name, raw in raw_by_filename.items()):
        raise ReviewDecisionPackageError("external decision bytes changed during validation")

    decision_dir.mkdir(exist_ok=True)
    for target, data in desired.items():
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(data)
    if any(target.read_bytes() != data for target, data in desired.items()):
        raise ReviewDecisionPackageError("packaged evidence failed byte readback")
    return {"decision_manifest": manifest, "review_progress": progress_artifact}


def _load_decision_jsonl(path: Path) -> list[Mapping[str, Any]]:
    return _read_jsonl(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts-dir",
        default=str(DEFAULT_STAGE_B_ARTIFACT_DIR),
        help="frozen local Stage B artifact directory",
    )
    parser.add_argument(
        "--review-dir",
        default=None,
        help="review output directory; defaults to <artifacts-dir>/review",
    )
    parser.add_argument(
        "--validate-decisions",
        default=None,
        help="validate an external JSONL decision file without writing it",
    )
    parser.add_argument(
        "--package-decisions",
        default=None,
        help="validate and preserve one complete external 12-packet decision directory",
    )
    args = parser.parse_args(argv)
    if args.validate_decisions is not None and args.package_decisions is not None:
        parser.error("--validate-decisions and --package-decisions are mutually exclusive")
    if args.validate_decisions is not None:
        decisions = _load_decision_jsonl(
            protocol.validate_local_path(args.validate_decisions, field="decision_path")
        )
        validated = validate_decisions(decisions, artifacts_dir=args.artifacts_dir)
        print(json.dumps(review_progress(validated, artifacts_dir=args.artifacts_dir), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if args.package_decisions is not None:
        result = package_independent_decisions(
            args.package_decisions,
            artifacts_dir=args.artifacts_dir,
            review_dir=(
                args.review_dir
                if args.review_dir is not None
                else protocol.validate_local_path(args.artifacts_dir, field="artifacts_dir") / "review"
            ),
        )
        print(json.dumps({
            "decision_manifest_sha256": result["decision_manifest"]["decision_manifest_sha256"],
            "review_progress_sha256": result["review_progress"]["review_progress_sha256"],
            "decision_count": result["review_progress"]["decision_count"],
            "accepted": result["review_progress"]["accepted"],
            "pending": result["review_progress"]["pending"],
        }, sort_keys=True, indent=2))
        return 0
    review_dir = (
        Path(args.review_dir)
        if args.review_dir is not None
        else protocol.validate_local_path(args.artifacts_dir, field="artifacts_dir") / "review"
    )
    result = build_review_artifacts(review_dir, artifacts_dir=args.artifacts_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
