"""Tests for the offline Stage B independent-review workflow."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_stage_b_independent_review as review  # noqa: E402


def _accept_decision(row: dict[str, object], *, reviewer: str = "independent-reviewer-a") -> dict[str, object]:
    return {
        "candidate_id": row["candidate_id"],
        "record_sha256": row["record_sha256"],
        "reviewer_role_id": reviewer,
        "decision": "accept",
        "reason_codes": list(review.POSITIVE_REASON_CODES),
    }


def _reject_decision(row: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_id": row["candidate_id"],
        "record_sha256": row["record_sha256"],
        "reviewer_role_id": "human-reviewer-1",
        "decision": "reject",
        "reason_codes": ["wrong_track_span"],
        "reviewer_note": "The track span is not exact.",
    }


def _first_packet_row(tmp_path: Path) -> dict[str, object]:
    result = review.build_review_artifacts(tmp_path / "review")
    packet_path = Path(result["review_dir"]) / "packets" / "packet-01.jsonl"
    return json.loads(packet_path.read_text(encoding="utf-8").splitlines()[0])


def test_review_source_binds_exact_reviewed_pr48_identities() -> None:
    source = review.load_review_source()

    assert dict(source.identities) == dict(review.REVIEWED_SOURCE_IDENTITIES)
    assert len(source.rows) == 3600
    assert len(source.entities_by_key) == 600


def test_source_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    copied = tmp_path / "stage_b"
    shutil.copytree(review.DEFAULT_STAGE_B_ARTIFACT_DIR, copied)
    manifest_path = copied / "candidate_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate_corpus_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(review.ReviewSourceIdentityError):
        review.load_review_source(copied)


def test_packets_cover_all_rows_once_with_fixed_sizes_and_no_split_labels(tmp_path: Path) -> None:
    result = review.build_review_artifacts(tmp_path / "review")
    review_dir = Path(result["review_dir"])
    packet_rows: list[dict[str, object]] = []
    for packet_number in range(1, 13):
        packet_path = review_dir / "packets" / f"packet-{packet_number:02d}.jsonl"
        rows = [json.loads(line) for line in packet_path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 300
        packet_rows.extend(rows)
        assert all(set(row) == review.PACKET_FIELD_SET for row in rows)
        assert all("split" not in row for row in rows)
        assert all(
            not any(term in packet_path.name.casefold() for term in ("train", "validation", "held"))
            for _row in rows[:1]
        )

    candidate_ids = [row["candidate_id"] for row in packet_rows]
    assert len(candidate_ids) == 3600
    assert len(set(candidate_ids)) == 3600
    assert set(candidate_ids) == {f"candidate-{number:05d}" for number in range(1, 3601)}


def test_packet_ids_and_hashes_are_deterministic(tmp_path: Path) -> None:
    first = review.build_review_artifacts(tmp_path / "first")
    second = review.build_review_artifacts(tmp_path / "second")

    assert first["manifest"] == second["manifest"]
    assert first["packet_hashes"] == second["packet_hashes"]
    for packet_number in range(1, 13):
        first_bytes = (
            Path(first["review_dir"]) / "packets" / f"packet-{packet_number:02d}.jsonl"
        ).read_bytes()
        second_bytes = (
            Path(second["review_dir"]) / "packets" / f"packet-{packet_number:02d}.jsonl"
        ).read_bytes()
        assert first_bytes == second_bytes


def test_each_packet_has_scope_language_template_slot_and_morphology_diversity(
    tmp_path: Path,
) -> None:
    manifest = review.build_review_artifacts(tmp_path / "review")["manifest"]

    assert manifest["packet_assignment"] == {
        "algorithm": "stratified_round_robin_v1",
        "packet_count": 12,
        "rows_per_packet": 300,
        "packets_are_not_splits": True,
    }
    for diversity in manifest["packet_diversity"].values():
        assert set(diversity["scope_counts"]) == {
            "supported_play",
            "supported_unknown",
            "deterministic_only",
            "safety_only",
        }
        assert set(diversity["language_counts"]) == {"zh-Hant", "zh-Hans", "mixed", "en"}
        assert len(diversity["template_family_counts"]) >= 8
        assert set(diversity["slot_mode_counts"]) >= {
            "both",
            "artist_only",
            "album_only",
            "neither",
            "not_applicable",
        }
        assert len(diversity["morphology_profile_counts"]) >= 4


def test_initial_manifest_has_zero_decisions_and_no_final_selection(tmp_path: Path) -> None:
    manifest = review.build_review_artifacts(tmp_path / "review")["manifest"]

    assert manifest["all_candidates_exactly_once"] is True
    assert manifest["decision_storage"] == {
        "directory": "decisions",
        "format": "JSONL",
        "submitted_decision_count": 0,
        "reviewed_candidate_count": 0,
        "accepted": 0,
        "rejected": 0,
        "needs_correction": 0,
        "pending": 3600,
    }
    assert manifest["final_split_assigned"] is False
    assert manifest["held_out_sealed"] is False
    assert manifest["training_authorized"] is False
    assert manifest["model_compute_authorized"] is False
    assert manifest["semantic_memory_enabled"] is False
    assert manifest["local_ai_fallback_approved"] is False


def test_decision_schema_rejects_extra_fields(tmp_path: Path) -> None:
    row = _first_packet_row(tmp_path)
    invalid = _accept_decision(row)
    invalid["extra"] = "not allowed"

    with pytest.raises(review.ReviewDecisionError):
        review.validate_decisions([invalid])


def test_unknown_candidate_id_is_rejected() -> None:
    invalid = {
        "candidate_id": "candidate-99999",
        "record_sha256": "0" * 64,
        "reviewer_role_id": "independent-reviewer-a",
        "decision": "reject",
        "reason_codes": ["other_review_blocker"],
    }

    with pytest.raises(review.ReviewDecisionError, match="unknown candidate_id"):
        review.validate_decisions([invalid])


def test_record_hash_mismatch_is_rejected() -> None:
    source = review.load_review_source()
    row = dict(source.rows[0])
    invalid = {
        "candidate_id": row["candidate_id"],
        "record_sha256": "0" * 64,
        "reviewer_role_id": "independent-reviewer-a",
        "decision": "reject",
        "reason_codes": ["wrong_scope"],
    }

    with pytest.raises(review.ReviewDecisionError, match="record_sha256"):
        review.validate_decisions([invalid])


def test_reviewer_role_must_be_opaque_and_nonempty() -> None:
    source = review.load_review_source()
    row = dict(source.rows[0])
    invalid = {
        "candidate_id": row["candidate_id"],
        "record_sha256": hashlib.sha256(
            review._canonical_json(row).encode("utf-8")
        ).hexdigest(),
        "reviewer_role_id": "reviewer@example.com",
        "decision": "reject",
        "reason_codes": ["other_review_blocker"],
    }

    with pytest.raises(review.ReviewDecisionError, match="reviewer_role_id"):
        review.validate_decisions([invalid])


def test_accept_requires_all_positive_evidence() -> None:
    source = review.load_review_source()
    row = dict(source.rows[0])
    invalid = {
        "candidate_id": row["candidate_id"],
        "record_sha256": review._sha256_json(row),
        "reviewer_role_id": "independent-reviewer-a",
        "decision": "accept",
        "reason_codes": ["label_correct"],
    }

    with pytest.raises(review.ReviewDecisionError, match="positive evidence"):
        review.validate_decisions([invalid])


def test_reject_and_needs_correction_require_negative_reason() -> None:
    source = review.load_review_source()
    row = dict(source.rows[0])
    for decision_value in ("reject", "needs_correction"):
        invalid = {
            "candidate_id": row["candidate_id"],
            "record_sha256": review._sha256_json(row),
            "reviewer_role_id": f"reviewer-{decision_value}",
            "decision": decision_value,
            "reason_codes": ["label_correct"],
        }
        with pytest.raises(review.ReviewDecisionError, match="negative reason"):
            review.validate_decisions([invalid])


def test_duplicate_decision_from_same_reviewer_is_rejected() -> None:
    source = review.load_review_source()
    row = dict(source.rows[0])
    decision = _accept_decision(
        {
            "candidate_id": row["candidate_id"],
            "record_sha256": review._sha256_json(row),
        }
    )

    with pytest.raises(review.ReviewDecisionError, match="duplicate decision"):
        review.validate_decisions([decision, dict(decision)])


def test_decisions_against_different_source_identity_are_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "stage_b"
    shutil.copytree(review.DEFAULT_STAGE_B_ARTIFACT_DIR, copied)
    config_path = copied / "generator_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["generator_version"] = "different-source"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(review.ReviewSourceIdentityError):
        review.validate_decisions([], artifacts_dir=copied)


def test_progress_is_zero_reviewed_and_3600_pending() -> None:
    progress = review.review_progress([])

    assert progress["total_candidates"] == 3600
    assert progress["decision_count"] == 0
    assert progress["reviewed"] == 0
    assert progress["accepted"] == 0
    assert progress["rejected"] == 0
    assert progress["needs_correction"] == 0
    assert progress["pending"] == 3600
    assert progress["by_packet"]
    assert progress["by_language"]
    assert progress["by_scope"]
    assert progress["by_template_family"]
    assert progress["by_slot_mode"]
    assert progress["by_reviewer_role"] == {}


def test_source_group_report_does_not_propagate_one_row_decision(tmp_path: Path) -> None:
    row = _first_packet_row(tmp_path)
    decision = _accept_decision(row)
    report = review.source_group_report([decision])
    group_id = str(row["source_group_id"])

    group = report[group_id]
    assert group["health"] == "unreviewed"
    assert group["direct_decision_count"] == 1
    assert group["reviewed_candidate_ids"] == [row["candidate_id"]]
    assert len(group["unreviewed_candidate_ids"]) == 5
    assert all(
        other["health"] == "unreviewed"
        for other_id, other in report.items()
        if other_id != group_id
    )


def test_build_does_not_rewrite_original_candidate_artifacts(tmp_path: Path) -> None:
    source_dir = review.DEFAULT_STAGE_B_ARTIFACT_DIR
    before = {
        path.name: path.read_bytes()
        for path in source_dir.iterdir()
        if path.is_file()
    }

    review.build_review_artifacts(tmp_path / "review")

    after = {
        path.name: path.read_bytes()
        for path in source_dir.iterdir()
        if path.is_file()
    }
    assert after == before


def test_workflow_has_no_automatic_review_or_runtime_dependencies() -> None:
    source_path = Path(review.__file__)
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        for alias in node.names
    )
    assert imported_roots.isdisjoint(
        {"requests", "httpx", "socket", "subprocess", "torch", "transformers"}
    )
    assert "def auto_accept" not in source_text
    assert "generate_accept" not in source_text
    assert "load_stage_a" not in source_text
    assert "spotify_uri" not in source_text
    assert "clarification_token" not in source_text


def test_review_manifest_self_hash_and_decision_readme_are_written(tmp_path: Path) -> None:
    result = review.build_review_artifacts(tmp_path / "review")
    review_dir = Path(result["review_dir"])
    manifest = json.loads((review_dir / "review_manifest.json").read_text(encoding="utf-8"))
    unsigned = dict(manifest)
    stored_hash = unsigned.pop("review_manifest_sha256")

    assert stored_hash == review._sha256_json(unsigned)
    assert (review_dir / "decisions" / "README.md").exists()
    assert "no independent reviewer decision" in (
        review_dir / "decisions" / "README.md"
    ).read_text(encoding="utf-8")
