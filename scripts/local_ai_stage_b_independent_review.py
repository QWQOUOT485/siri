"""Prepare deterministic packets for independent review of Stage B candidates.

This module is deliberately downstream of the frozen candidate artifacts.  It
does not generate, relabel, rewrite, accept, reject, split, or train on a
candidate.  The only writes it performs are review packets, a review manifest,
and reviewer-facing schema documentation under the separate ``review``
directory.

The source identity is fail-closed against the reviewed PR #48 artifact
hashes.  A regenerated candidate corpus therefore cannot silently reuse an
old review workflow or decision ledger.
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


REVIEW_WORKFLOW_VERSION = "stage-b-independent-review-v1"
REVIEW_STATUS = "pending_independent_review"
PACKET_COUNT = 12
ROWS_PER_PACKET = 300
EXPECTED_CANDIDATE_COUNT = PACKET_COUNT * ROWS_PER_PACKET
DEFAULT_STAGE_B_ARTIFACT_DIR = _REPO_ROOT / "artifacts" / "local_ai" / "stage_b"
DEFAULT_REVIEW_DIR = DEFAULT_STAGE_B_ARTIFACT_DIR / "review"

# These are the reviewed PR #48 source identities.  They are intentionally
# literal and independent of the current candidate manifest.  The manifest is
# also recomputed and compared so a stale or hand-edited manifest cannot bless
# a different source corpus.
REVIEWED_SOURCE_IDENTITIES = MappingProxyType(
    {
        "candidate_corpus_sha256": (
            "c7e0a44b69d4033c960a8a1af20b0f4c71ad5674ece4b9a44953a1bea40e68d2"
        ),
        "entity_catalog_sha256": (
            "5deb5bd5a5c7d02b0f2eb864d0bfc4063161c62697d19fc2363f9d3e458b502a"
        ),
        "generator_config_sha256": (
            "d263bd9ec97a897134e9fc5bf1121f16b86a84ff9a361d7046c68f10670d4435"
        ),
        "candidate_manifest_sha256": (
            "a2ceef6205a3bf1a92c31a6ad12d34ac5a1d9aee467ace101532ba9ddfae074f"
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


class ReviewWorkflowError(ValueError):
    """Base class for deterministic review workflow failures."""


class ReviewSourceIdentityError(ReviewWorkflowError):
    """The source artifacts do not match the reviewed candidate corpus."""


class ReviewPacketError(ReviewWorkflowError):
    """The packet assignment or packet artifact is invalid."""


class ReviewDecisionError(ReviewWorkflowError):
    """A reviewer decision violates the closed submission schema."""


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
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
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
    if payload["generator_version"] != "stage-b-candidate-generator-v4":
        raise ReviewSourceIdentityError("candidate row generator version is not v4")
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
    """Load and fail-closed validate the reviewed PR #48 source artifacts."""

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
            "source artifacts do not match the reviewed PR #48 identities"
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
        "review_manifest_version": 1,
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
            "submitted_decision_count": 0,
            "reviewed_candidate_count": 0,
            "accepted": 0,
            "rejected": 0,
            "needs_correction": 0,
            "pending": EXPECTED_CANDIDATE_COUNT,
        },
        "decision_schema": _decision_schema_payload(),
        "source_group_reporting": {
            "row_level_decisions": True,
            "auto_propagate_decisions": False,
            "fully_accepted_requires_each_row": True,
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
submitted. `review_manifest.json` records `reviewed_candidate_count=0` and
`pending=3600`.

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
decision to the reviewed PR #48 source identities and rejects duplicate
decisions from the same reviewer for the same candidate.

Do not add provider IDs, credentials, OAuth data, private paths, user IDs,
clarification tokens, production authority data, or split labels. Do not edit
the candidate corpus or silently rewrite a candidate. `needs_correction`
rows remain excluded from later selection until a separate reviewed correction
workflow exists.

This is a human/external-reviewer input boundary. Passing unit tests or the
production-alignment gate is supporting evidence only and never creates an
accept decision.

To validate a local JSONL submission without writing a ledger:

```text
.venv\\Scripts\\python.exe scripts\\local_ai_stage_b_independent_review.py --validate-decisions <decisions.jsonl>
```

The validator is offline-only and fails closed if the candidate artifact
identity differs from the reviewed PR #48 hashes in the review manifest.
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
    (decision_dir / "README.md").write_text(
        _decisions_readme(manifest),
        encoding="utf-8",
    )
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


def _progress_dimension(
    decisions: Sequence[Mapping[str, Any]],
    key_for_candidate: Mapping[str, str],
) -> dict[str, dict[str, int]]:
    decision_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reviewed: dict[str, set[str]] = defaultdict(set)
    for decision in decisions:
        key = key_for_candidate[decision["candidate_id"]]
        decision_counts[key][decision["decision"]] += 1
        reviewed[key].add(decision["candidate_id"])
    keys = sorted(set(key_for_candidate.values()))
    return {
        key: {
            "decision_count": decision_counts[key].total(),
            "reviewed_candidates": len(reviewed[key]),
            "accepted": decision_counts[key]["accept"],
            "rejected": decision_counts[key]["reject"],
            "needs_correction": decision_counts[key]["needs_correction"],
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
            "reviewed_candidates": len(reviewed[role]),
            "accepted": decision_counts[role]["accept"],
            "rejected": decision_counts[role]["reject"],
            "needs_correction": decision_counts[role]["needs_correction"],
        }
        for role in sorted(decision_counts)
    }


def review_progress(
    decisions: Sequence[Mapping[str, Any]],
    *,
    artifacts_dir: str | Path = DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Return row-level progress dimensions without creating a ledger."""

    source = load_review_source(artifacts_dir)
    validated = _validate_decisions_against_source(decisions, source)
    packet_by_candidate = _packet_map(source)
    row_by_id = source.rows_by_id
    prepared_by_id = {
        item.row["candidate_id"]: item for item in _prepared_candidates(source)
    }
    reviewed_ids = {decision["candidate_id"] for decision in validated}
    decision_counts = Counter(decision["decision"] for decision in validated)
    return {
        "total_candidates": len(source.rows),
        "decision_count": len(validated),
        "reviewed": len(reviewed_ids),
        "accepted": decision_counts["accept"],
        "rejected": decision_counts["reject"],
        "needs_correction": decision_counts["needs_correction"],
        "pending": len(source.rows) - len(reviewed_ids),
        "by_packet": _progress_dimension(validated, packet_by_candidate),
        "by_language": _progress_dimension(
            validated,
            {candidate_id: str(row["language_tag"]) for candidate_id, row in row_by_id.items()},
        ),
        "by_scope": _progress_dimension(
            validated,
            {candidate_id: item.scope for candidate_id, item in prepared_by_id.items()},
        ),
        "by_template_family": _progress_dimension(
            validated,
            {
                candidate_id: str(row["template_family"])
                for candidate_id, row in row_by_id.items()
            },
        ),
        "by_slot_mode": _progress_dimension(
            validated,
            {candidate_id: item.slot_mode for candidate_id, item in prepared_by_id.items()},
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
        decisions_by_candidate: dict[str, list[str]] = defaultdict(list)
        for decision in group_decisions:
            decisions_by_candidate[decision["candidate_id"]].append(decision["decision"])
        reviewed_ids = sorted(decisions_by_candidate)
        decision_values = [value for values in decisions_by_candidate.values() for value in values]
        if not decision_values:
            health = "unreviewed"
        elif "needs_correction" in decision_values:
            health = "needs_correction"
        elif "reject" in decision_values:
            health = "partially_rejected"
        elif all(
            candidate_id in decisions_by_candidate
            and set(decisions_by_candidate[candidate_id]) == {"accept"}
            for candidate_id in candidate_ids
        ):
            health = "fully_accepted"
        else:
            health = "unreviewed"
        report[group_id] = {
            "health": health,
            "candidate_count": len(candidate_ids),
            "reviewed_candidate_ids": reviewed_ids,
            "unreviewed_candidate_ids": [
                candidate_id for candidate_id in candidate_ids if candidate_id not in reviewed_ids
            ],
            "direct_decision_count": len(group_decisions),
            "decision_counts": dict(sorted(Counter(decision_values).items())),
        }
    return report


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
    args = parser.parse_args(argv)
    if args.validate_decisions is not None:
        decisions = _load_decision_jsonl(
            protocol.validate_local_path(args.validate_decisions, field="decision_path")
        )
        validated = validate_decisions(decisions, artifacts_dir=args.artifacts_dir)
        print(json.dumps(review_progress(validated, artifacts_dir=args.artifacts_dir), ensure_ascii=False, sort_keys=True, indent=2))
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
