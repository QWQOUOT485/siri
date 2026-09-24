"""Deterministic, offline Stage B v6 whole-group final selection before sealing."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import local_ai_stage_b_corpus as protocol
import local_ai_stage_b_independent_review as review


STARTING_MAIN_SHA = "7619baa4145b7525fad32a1bc62ec35afedd59aa"
DECISION_MANIFEST_SHA256 = "a6bce0eaba3b2e68f7ee11b0f6cd3318664e277df5430be0ef187d94b23fa39d"
REVIEW_PROGRESS_SHA256 = "4defbb52301054d0a82c99939e930094ed2be3fe89512cb7959a3349287ec5ce"
SELECTION_VERSION = "stage-b-final-selection-v1"
ASSIGNMENT_VERSION = "lex-first-heldout-then-train-validation-v1"
DEFAULT_OUTPUT_DIR = protocol.REPO_ROOT / "artifacts" / "local_ai" / "stage_b" / "final_v1"
CLASS_KEYS = ("supported_play", "supported_unknown", "deterministic_only", "safety_only")
GROUP_TARGETS = {
    "train": {"supported_play": 150, "supported_unknown": 100, "deterministic_only": 30, "safety_only": 20},
    "validation": {"supported_play": 50, "supported_unknown": 40, "deterministic_only": 5, "safety_only": 5},
    "test": {"supported_play": 50, "supported_unknown": 40, "deterministic_only": 5, "safety_only": 5},
}


class FinalSelectionError(ValueError):
    """Frozen source, review, assignment, or output evidence failed closed."""


@dataclass(frozen=True)
class VerifiedInputs:
    source: review.ReviewSource
    decisions: tuple[Mapping[str, Any], ...]
    decision_manifest: Mapping[str, Any]
    review_progress: Mapping[str, Any]


@dataclass(frozen=True)
class SourceGroup:
    group_id: str
    class_key: str
    rows: tuple[Mapping[str, Any], ...]


def _require_accepted_coverage(
    decisions: Sequence[Mapping[str, Any]], candidate_ids: set[str]
) -> None:
    reviewed_ids = [item["candidate_id"] for item in decisions]
    if len(decisions) != 3600 or len(set(reviewed_ids)) != 3600 or set(reviewed_ids) != candidate_ids:
        raise FinalSelectionError("review decisions do not cover 3,600 candidates exactly once")
    if any(item["decision"] != "accept" for item in decisions):
        raise FinalSelectionError("final selection requires every frozen candidate to be accepted")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(protocol.canonical_json(value).encode("utf-8")).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FinalSelectionError(f"invalid frozen JSON artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise FinalSelectionError(f"frozen JSON artifact is not an object: {path.name}")
    return value


def _verify_self_hash(value: Mapping[str, Any], field: str, expected: str) -> None:
    unsigned = dict(value)
    if unsigned.pop(field, None) != expected or _canonical_hash(unsigned) != expected:
        raise FinalSelectionError(f"frozen {field} identity mismatch")


def load_verified_inputs(
    artifacts_dir: Path = review.DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> VerifiedInputs:
    """Validate frozen v6, raw submissions, package identity, and aggregate."""

    source = review.load_review_source(artifacts_dir)
    review_dir = source.artifact_dir / "review"
    manifest = _read_object(review_dir / "decision_manifest.json")
    progress_artifact = _read_object(review_dir / "review_progress.json")
    _verify_self_hash(manifest, "decision_manifest_sha256", DECISION_MANIFEST_SHA256)
    _verify_self_hash(progress_artifact, "review_progress_sha256", REVIEW_PROGRESS_SHA256)
    if (
        manifest.get("decision_package_version") != review.DECISION_PACKAGE_VERSION
        or manifest.get("source_identities") != dict(source.identities)
        or manifest.get("package_status") != "complete_exact_once"
        or manifest.get("coverage_exact") is not True
        or manifest.get("decision_count") != 3600
        or manifest.get("unique_candidate_count") != 3600
        or manifest.get("duplicate_candidate_count") != 0
        or progress_artifact.get("source_identities") != dict(source.identities)
        or progress_artifact.get("decision_manifest_sha256") != DECISION_MANIFEST_SHA256
    ):
        raise FinalSelectionError("frozen decision package metadata mismatch")

    packet_map = review._packet_map(source)
    decision_dir = review_dir / "decisions"
    expected_names = {f"packet-{number:02d}.decisions.jsonl" for number in range(1, 13)}
    if not decision_dir.is_dir() or {
        path.name for path in decision_dir.iterdir() if path.suffix == ".jsonl"
    } != expected_names:
        raise FinalSelectionError("packaged decision file set is not exact")
    decisions: list[Mapping[str, Any]] = []
    for number in range(1, 13):
        packet_id = f"packet-{number:02d}"
        filename = f"{packet_id}.decisions.jsonl"
        path = decision_dir / filename
        if path.is_symlink() or not path.is_file():
            raise FinalSelectionError("packaged decision file is missing or redirected")
        raw = path.read_bytes()
        rows = review._decision_jsonl_from_bytes(raw, filename=filename)
        entry = manifest.get("packet_files", {}).get(packet_id)
        if (
            len(rows) != 300
            or not isinstance(entry, Mapping)
            or entry.get("filename") != filename
            or entry.get("row_count") != 300
            or entry.get("packaged_sha256") != _sha256(raw)
            or entry.get("external_source_sha256") != _sha256(raw)
            or {row.get("candidate_id") for row in rows}
            != {candidate_id for candidate_id, assigned in packet_map.items() if assigned == packet_id}
        ):
            raise FinalSelectionError(f"packaged packet identity or assignment mismatch: {packet_id}")
        decisions.extend(rows)

    validated = review._validate_decisions_against_source(decisions, source)
    _require_accepted_coverage(validated, set(source.rows_by_id))
    computed_progress = review.review_progress(validated, artifacts_dir=source.artifact_dir)
    if any(progress_artifact.get(key) != value for key, value in computed_progress.items()):
        raise FinalSelectionError("stored review progress disagrees with raw decisions")
    if (
        computed_progress["accepted"] != 3600
        or any(computed_progress[name] != 0 for name in ("rejected", "needs_correction", "conflict", "pending"))
        or manifest.get("raw_decision_counts") != computed_progress["raw_decision_counts"]
        or manifest.get("reviewer_role_ids") != sorted({item["reviewer_role_id"] for item in validated})
    ):
        raise FinalSelectionError("review aggregate is not complete all-accepted coverage")
    return VerifiedInputs(source, tuple(validated), manifest, progress_artifact)


def _groups(source: review.ReviewSource) -> dict[str, SourceGroup]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in source.rows:
        grouped[str(row["source_group_id"])].append(row)
    if len(grouped) != 600:
        raise FinalSelectionError("source group count is not 600")
    result: dict[str, SourceGroup] = {}
    for group_id, rows in sorted(grouped.items()):
        classes = {review._review_scope(row) for row in rows}
        if len(rows) != 6 or len(classes) != 1:
            raise FinalSelectionError("source group is not six-row class-homogeneous")
        result[group_id] = SourceGroup(
            group_id, classes.pop(), tuple(sorted(rows, key=lambda row: row["candidate_id"]))
        )
    if Counter(group.class_key for group in result.values()) != {
        "supported_play": 300, "supported_unknown": 210,
        "deterministic_only": 50, "safety_only": 40,
    }:
        raise FinalSelectionError("source group class shape differs from frozen v6")
    return result


def _features(group: SourceGroup, names: Sequence[str]) -> tuple[int, ...]:
    values: Counter[str] = Counter()
    for row in group.rows:
        language = row["language_tag"]
        if language in ("zh-Hant", "mixed"):
            values[language] += 1
        if group.class_key == "supported_play":
            status = row["provisional_optional_slot_status"]
            for slot in ("artist", "album"):
                values[f"{slot}_{status[slot]}"] += 1
    return tuple(values[name] for name in names)


def _lex_first_subset(
    groups: Sequence[SourceGroup], count: int, names: Sequence[str], minima: Sequence[int]
) -> tuple[str, ...]:
    """Include each sorted group first iff a full valid completion exists."""

    ordered = sorted(groups, key=lambda group: group.group_id)
    feature_rows = [_features(group, names) for group in ordered]
    suffix = [[0] * len(names) for _ in range(len(ordered) + 1)]
    for index in range(len(ordered) - 1, -1, -1):
        suffix[index] = [a + b for a, b in zip(feature_rows[index], suffix[index + 1])]
    minima_tuple = tuple(minima)

    @lru_cache(maxsize=None)
    def feasible(index: int, selected: int, reached: tuple[int, ...]) -> bool:
        slots = count - selected
        if slots < 0 or len(ordered) - index < slots:
            return False
        if any(reached[j] + min(suffix[index][j], 6 * slots) < minima_tuple[j] for j in range(len(names))):
            return False
        if slots == 0:
            return all(reached[j] >= minima_tuple[j] for j in range(len(names)))
        if index == len(ordered):
            return False
        included = tuple(min(minima_tuple[j], reached[j] + feature_rows[index][j]) for j in range(len(names)))
        return feasible(index + 1, selected + 1, included) or feasible(index + 1, selected, reached)

    state = tuple(0 for _ in names)
    if not feasible(0, 0, state):
        raise FinalSelectionError("no whole-group assignment satisfies frozen held-out coverage")
    chosen: list[str] = []
    for index, group in enumerate(ordered):
        if len(chosen) == count:
            break
        included = tuple(min(minima_tuple[j], state[j] + feature_rows[index][j]) for j in range(len(names)))
        if feasible(index + 1, len(chosen) + 1, included):
            chosen.append(group.group_id)
            state = included
    if len(chosen) != count:
        raise FinalSelectionError("held-out reconstruction failed")
    return tuple(chosen)


def assign_groups(groups: Mapping[str, SourceGroup]) -> dict[str, str]:
    """Choose lex-first feasible held-out groups, then lex-first remaining splits."""

    by_class = {
        key: sorted((group for group in groups.values() if group.class_key == key), key=lambda g: g.group_id)
        for key in CLASS_KEYS
    }
    play_names = ("zh-Hant", "mixed", "artist_present", "artist_absent", "album_present", "album_absent")
    play_minima = (40, 40, 150, 100, 100, 150)
    held_play = _lex_first_subset(by_class["supported_play"], 50, play_names, play_minima)
    play_rows = [row for group_id in held_play for row in groups[group_id].rows]
    play_language = Counter(row["language_tag"] for row in play_rows)
    unknown_minima = (max(40, 100 - play_language["zh-Hant"]), max(40, 100 - play_language["mixed"]))
    held_unknown = _lex_first_subset(by_class["supported_unknown"], 40, ("zh-Hant", "mixed"), unknown_minima)
    held_out = set(held_play + held_unknown)
    for class_key in ("deterministic_only", "safety_only"):
        held_out.update(group.group_id for group in by_class[class_key][:5])

    assignment = {group_id: "test" for group_id in held_out}
    for class_key in CLASS_KEYS:
        remaining = [group.group_id for group in by_class[class_key] if group.group_id not in held_out]
        train_count = GROUP_TARGETS["train"][class_key]
        validation_count = GROUP_TARGETS["validation"][class_key]
        for group_id in remaining[:train_count]:
            assignment[group_id] = "train"
        for group_id in remaining[train_count:train_count + validation_count]:
            assignment[group_id] = "validation"
        for group_id in remaining[train_count + validation_count:]:
            assignment[group_id] = "excluded"
    if set(assignment) != set(groups):
        raise FinalSelectionError("assignment does not cover all source groups")
    for split in protocol.SPLIT_NAMES:
        if Counter(groups[group_id].class_key for group_id, state in assignment.items() if state == split) != GROUP_TARGETS[split]:
            raise FinalSelectionError("whole-group split quotas were not met")
    return dict(sorted(assignment.items()))


def _record(row: Mapping[str, Any]) -> protocol.StageBRecord:
    return protocol.StageBRecord.from_mapping({
        "case_id": row["candidate_id"],
        "source_group_id": row["source_group_id"],
        "utterance": row["utterance"],
        "language_tag": row["language_tag"],
        "language_slice": row["language_slice"],
        "ai_scope": row["provisional_ai_scope"],
        "expected": row["provisional_expected"],
        "optional_slot_status": row["provisional_optional_slot_status"],
        "negative_reason": row["provisional_negative_reason"],
        "template_family": row["template_family"],
        "generator_version": row["generator_version"],
    })


def _jsonl_bytes(records: Sequence[protocol.StageBRecord]) -> bytes:
    return b"".join(
        protocol.canonical_json(record.to_dict()).encode("utf-8") + b"\n"
        for record in sorted(records, key=lambda record: record.case_id)
    )


README = """# Stage B final v1 pre-seal corpus

These 3,000 rows were selected from the frozen, independently accepted v6 pool
using a deterministic whole-source-group assignment. `held_out.jsonl` is an
assigned Stage B test split, but it is **not sealed**. No training, model compute,
calibration, benchmark promotion, Semantic Memory, or Local AI fallback is
authorized by these artifacts. The 600 excluded candidates remain in frozen v6.

`selection_manifest.json` binds input identities, output hashes, quotas, and
coverage. `corpus_manifest.json` is the authoritative protocol validator's
result. `provenance_manifest.json` records sanitized review provenance.
"""


def build_final_artifacts(
    *,
    artifacts_dir: Path = review.DEFAULT_STAGE_B_ARTIFACT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    verified = load_verified_inputs(artifacts_dir)
    groups = _groups(verified.source)
    if protocol.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256 != protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256:
        raise FinalSelectionError("frozen near-duplicate configuration mismatch")
    assignment = assign_groups(groups)
    splits = {
        split: tuple(_record(row) for group_id, group in groups.items() if assignment[group_id] == split for row in group.rows)
        for split in protocol.SPLIT_NAMES
    }
    # Stage A is read only here, after assignment has been fixed.
    validated = protocol.validate_protocol_corpus(splits, verify_stage_a_identity=True)
    corpus_manifest = validated.manifest_dict()
    if corpus_manifest["near_duplicate_policy"]["config_sha256"] != protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256:
        raise FinalSelectionError("authoritative validator near-duplicate identity mismatch")
    source_values = {row["generation_source"] for row in verified.source.rows}
    role_ids = verified.decision_manifest["reviewer_role_ids"]
    if len(source_values) != 1 or len(role_ids) != 1:
        raise FinalSelectionError("generation source or reviewer role is not singular")
    provenance = protocol.build_provenance_manifest(
        validated,
        corpus_protocol_version="stage-b-corpus-build-v1",
        generator_version="stage-b-candidate-generator-v6",
        generation_source=source_values.pop(),
        reviewer_role_id=role_ids[0],
        review_status="independently_reviewed",
        review_timestamp_policy="omitted-no-personal-timestamp",
        split_assignment_stage="group-aware-pre-seal",
        validation_tool_version=SELECTION_VERSION,
    )
    group_entries = {
        group_id: {
            "state": assignment[group_id],
            "class": group.class_key,
            "candidate_ids": [row["candidate_id"] for row in group.rows],
            "membership_sha256": _canonical_hash([row["candidate_id"] for row in group.rows]),
        }
        for group_id, group in groups.items()
    }
    split_assignment: dict[str, Any] = {
        "assignment_version": ASSIGNMENT_VERSION,
        "starting_main_sha": STARTING_MAIN_SHA,
        "source_identities": dict(verified.source.identities),
        "decision_manifest_sha256": DECISION_MANIFEST_SHA256,
        "review_progress_sha256": REVIEW_PROGRESS_SHA256,
        "groups": group_entries,
        "group_state_counts": dict(sorted(Counter(assignment.values()).items())),
        "final_split_assigned": True,
        "held_out_sealed": False,
    }
    split_assignment["split_assignment_sha256"] = _canonical_hash(split_assignment)

    files: dict[str, bytes] = {
        "train.jsonl": _jsonl_bytes(splits["train"]),
        "validation.jsonl": _jsonl_bytes(splits["validation"]),
        "held_out.jsonl": _jsonl_bytes(splits["test"]),
        "split_assignment.json": _json_bytes(split_assignment),
        "corpus_manifest.json": _json_bytes(corpus_manifest),
        "provenance_manifest.json": _json_bytes(provenance),
        "README.md": README.encode("utf-8"),
    }
    per_split_group_counts = {
        split: dict(sorted(Counter(groups[group_id].class_key for group_id, state in assignment.items() if state == split).items()))
        for split in (*protocol.SPLIT_NAMES, "excluded")
    }
    selection_manifest: dict[str, Any] = {
        "selection_schema_version": SELECTION_VERSION,
        "starting_main_sha": STARTING_MAIN_SHA,
        "source_identities": dict(verified.source.identities),
        "decision_manifest_sha256": DECISION_MANIFEST_SHA256,
        "review_progress_sha256": REVIEW_PROGRESS_SHA256,
        "selection_algorithm": ASSIGNMENT_VERSION,
        "source_row_count": len(verified.source.rows),
        "source_group_count": len(groups),
        "review_counts": {key: verified.review_progress[key] for key in ("accepted", "rejected", "needs_correction", "conflict", "pending")},
        "selected_row_count": 3000,
        "selected_group_count": 500,
        "excluded_row_count": 600,
        "excluded_group_count": 100,
        "overall_class_counts": {
            key: sum(corpus_manifest["per_split_class_counts"][split][key] for split in protocol.SPLIT_NAMES)
            for key in CLASS_KEYS
        },
        "per_split_row_counts": corpus_manifest["per_split_row_counts"],
        "per_split_class_counts": corpus_manifest["per_split_class_counts"],
        "per_split_group_counts": dict(sorted(Counter(assignment.values()).items())),
        "per_split_group_class_counts": per_split_group_counts,
        "per_split_language_counts": corpus_manifest["per_split_language_tag_counts"],
        "per_split_template_family_counts": {
            split: dict(sorted(Counter(record.template_family for record in splits[split]).items()))
            for split in protocol.SPLIT_NAMES
        },
        "per_split_negative_reason_counts": {
            split: dict(sorted(Counter(record.negative_reason for record in splits[split] if record.negative_reason is not None).items()))
            for split in protocol.SPLIT_NAMES
        },
        "per_split_optional_slot_counts": corpus_manifest["per_split_optional_slot_counts"],
        "held_out_language_gates": corpus_manifest["held_out_language_gates"],
        "held_out_optional_slots": protocol.optional_slot_partition(splits["test"], require_protocol_partition=True),
        "stage_a_sha256": protocol.EXPECTED_STAGE_A_SHA256,
        "near_duplicate_config_sha256": protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256,
        "canonical_corpus_sha256": corpus_manifest["corpus_sha256"],
        "canonical_split_sha256": corpus_manifest["split_sha256"],
        "artifact_file_sha256": {name: _sha256(data) for name, data in sorted(files.items())},
        "final_split_assigned": True,
        "held_out_sealed": False,
        "training_authorized": False,
        "model_compute_authorized": False,
        "semantic_memory_enabled": False,
        "local_ai_fallback_approved": False,
    }
    selection_manifest["selection_manifest_sha256"] = _canonical_hash(selection_manifest)
    files["selection_manifest.json"] = _json_bytes(selection_manifest)

    target_dir = protocol.validate_local_path(output_dir, field="output_dir")
    if target_dir.is_symlink() or (target_dir.exists() and not target_dir.is_dir()):
        raise FinalSelectionError("final output target is not a local directory")
    if target_dir.exists():
        if {path.name for path in target_dir.iterdir()} - set(files):
            raise FinalSelectionError("unexpected existing final artifact")
        if any((target_dir / name).is_symlink() or ((target_dir / name).exists() and (target_dir / name).read_bytes() != data) for name, data in files.items()):
            raise FinalSelectionError("refusing to overwrite conflicting final artifacts")
    else:
        target_dir.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        if not (target_dir / name).exists():
            with (target_dir / name).open("xb") as stream:
                stream.write(data)
    if any((target_dir / name).read_bytes() != data for name, data in files.items()):
        raise FinalSelectionError("final artifact write readback mismatch")
    return selection_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=review.DEFAULT_STAGE_B_ARTIFACT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    manifest = build_final_artifacts(artifacts_dir=args.artifacts_dir, output_dir=args.output_dir)
    print(json.dumps({key: manifest[key] for key in ("selection_manifest_sha256", "canonical_corpus_sha256", "per_split_row_counts")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
