"""Offline complete-set packaging tests for frozen Stage B v6 review decisions."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_stage_b_independent_review as review  # noqa: E402


def _packet_name(number: int) -> str:
    return f"packet-{number:02d}.decisions.jsonl"


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_bytes(
        b"".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
            for row in rows
        )
    )


def _read_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def synthetic_external_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    external = tmp_path_factory.mktemp("stage-b-v6-external-decisions")
    packet_dir = review.DEFAULT_REVIEW_DIR / "packets"
    for number in range(1, 13):
        packet_rows = _read_rows(packet_dir / f"packet-{number:02d}.jsonl")
        decisions = [
            {
                "candidate_id": row["candidate_id"],
                "record_sha256": row["record_sha256"],
                "reviewer_role_id": "synthetic-independent-reviewer",
                "decision": "accept",
                "reason_codes": list(review.POSITIVE_REASON_CODES),
            }
            for row in packet_rows
        ]
        _write_rows(external / _packet_name(number), decisions)
    (external / review.EXTERNAL_REVIEW_REPORT_NAME).write_text(
        "Supporting report; not a decision source.\n", encoding="utf-8"
    )
    return external


@pytest.fixture
def package_work(
    tmp_path: Path,
    synthetic_external_dir: Path,
) -> tuple[Path, Path]:
    external = tmp_path / "external"
    artifacts = tmp_path / "stage_b_v6"
    shutil.copytree(synthetic_external_dir, external)
    shutil.copytree(
        review.DEFAULT_STAGE_B_ARTIFACT_DIR,
        artifacts,
        ignore=shutil.ignore_patterns("*.decisions.jsonl", "decision_manifest.json", "review_progress.json"),
    )
    return external, artifacts


def _package(external: Path, artifacts: Path) -> dict[str, object]:
    return review.package_independent_decisions(
        external, artifacts_dir=artifacts, review_dir=artifacts / "review"
    )


def _change_first_decision(external: Path, change: dict[str, object]) -> None:
    path = external / _packet_name(1)
    rows = _read_rows(path)
    rows[0].update(change)
    _write_rows(path, rows)


def test_complete_package_preserves_raw_bytes_and_initial_manifest(
    package_work: tuple[Path, Path],
) -> None:
    external, artifacts = package_work
    review_dir = artifacts / "review"
    initial_bytes = (review_dir / "review_manifest.json").read_bytes()
    result = _package(external, artifacts)
    manifest = result["decision_manifest"]
    progress = result["review_progress"]

    assert (review_dir / "review_manifest.json").read_bytes() == initial_bytes
    assert manifest["source_identities"] == dict(review.REVIEWED_SOURCE_IDENTITIES)
    assert manifest["reviewed_git_head"] == review.REVIEWED_V6_GIT_HEAD
    assert manifest["merged_main_baseline"] == review.V6_MERGED_MAIN_BASELINE
    assert manifest["reviewer_role_ids"] == ["synthetic-independent-reviewer"]
    assert manifest["decision_count"] == manifest["unique_candidate_count"] == 3600
    assert manifest["duplicate_candidate_count"] == 0
    assert manifest["coverage_exact"] is True
    assert manifest["packet_assignment"]["packets_are_not_splits"] is True
    assert manifest["training_authorized"] is False
    assert manifest["model_compute_authorized"] is False
    assert manifest["external_review_report"]["sha256"] == hashlib.sha256(
        (external / review.EXTERNAL_REVIEW_REPORT_NAME).read_bytes()
    ).hexdigest()

    for number in range(1, 13):
        name = _packet_name(number)
        original = (external / name).read_bytes()
        packaged = (review_dir / "decisions" / name).read_bytes()
        entry = manifest["packet_files"][f"packet-{number:02d}"]
        assert original == packaged
        assert entry["row_count"] == 300
        assert entry["external_source_sha256"] == entry["packaged_sha256"] == hashlib.sha256(original).hexdigest()

    for key, value in {
        "total_candidates": 3600,
        "decision_count": 3600,
        "reviewed": 3600,
        "accepted": 3600,
        "rejected": 0,
        "needs_correction": 0,
        "conflict": 0,
        "pending": 0,
    }.items():
        assert progress[key] == value
    assert progress["raw_decision_counts"] == {
        "accept": 3600, "reject": 0, "needs_correction": 0,
    }
    for dimension in (
        "by_packet", "by_language", "by_scope", "by_template_family",
        "by_slot_mode", "by_reviewer_role",
    ):
        assert progress[dimension]
    assert len(progress["by_packet"]) == 12
    assert progress["by_reviewer_role"]["synthetic-independent-reviewer"]["decision_count"] == 3600
    with pytest.raises(review.ReviewWorkflowError, match="refusing to overwrite"):
        review.build_review_artifacts(review_dir, artifacts_dir=artifacts)


def test_package_is_deterministic_and_identical_rerun_is_safe(
    package_work: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    external, artifacts = package_work
    first = _package(external, artifacts)
    review_dir = artifacts / "review"
    first_manifest = (review_dir / "decision_manifest.json").read_bytes()
    first_progress = (review_dir / "review_progress.json").read_bytes()
    assert _package(external, artifacts) == first
    assert (review_dir / "decision_manifest.json").read_bytes() == first_manifest
    assert (review_dir / "review_progress.json").read_bytes() == first_progress

    other = tmp_path / "other_stage_b_v6"
    shutil.copytree(
        review.DEFAULT_STAGE_B_ARTIFACT_DIR,
        other,
        ignore=shutil.ignore_patterns("*.decisions.jsonl", "decision_manifest.json", "review_progress.json"),
    )
    _package(external, other)
    assert (other / "review" / "decision_manifest.json").read_bytes() == first_manifest
    assert (other / "review" / "review_progress.json").read_bytes() == first_progress


@pytest.mark.parametrize("fault", ["missing", "extra", "malformed", "duplicate_key", "short", "long"])
def test_packet_file_set_and_jsonl_fail_closed(
    package_work: tuple[Path, Path], fault: str,
) -> None:
    external, artifacts = package_work
    path = external / _packet_name(1)
    if fault == "missing":
        path.unlink()
    elif fault == "extra":
        (external / "packet-13.decisions.jsonl").write_bytes(path.read_bytes())
    elif fault == "malformed":
        path.write_bytes(b"{bad json}\n")
    elif fault == "duplicate_key":
        rows = path.read_text(encoding="utf-8").splitlines()
        rows[0] = rows[0].replace('"candidate_id":', '"candidate_id":"shadow", "candidate_id":', 1)
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    else:
        rows = _read_rows(path)
        if fault == "short":
            rows.pop()
        else:
            rows.append(dict(rows[0]))
        _write_rows(path, rows)
    with pytest.raises(review.ReviewWorkflowError):
        _package(external, artifacts)
    assert not (artifacts / "review" / "decision_manifest.json").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"unexpected": True},
        {"candidate_id": "candidate-99999"},
        {"record_sha256": "0" * 64},
        {"reviewer_role_id": "reviewer@example.com"},
        {"decision": "maybe"},
        {"reason_codes": ["not_a_reason"]},
        {"reason_codes": ["label_correct"]},
        {"decision": "reject", "reason_codes": ["label_correct"]},
        {"decision": "needs_correction", "reason_codes": ["scope_correct"]},
    ],
)
def test_invalid_decision_schema_fails_closed(
    package_work: tuple[Path, Path], change: dict[str, object],
) -> None:
    external, artifacts = package_work
    _change_first_decision(external, change)
    with pytest.raises(review.ReviewWorkflowError):
        _package(external, artifacts)
    assert not (artifacts / "review" / "decision_manifest.json").exists()


def test_duplicate_candidate_and_wrong_packet_assignment_are_rejected(
    package_work: tuple[Path, Path],
) -> None:
    external, artifacts = package_work
    path = external / _packet_name(1)
    original = _read_rows(path)
    rows = list(original)
    rows[1] = dict(rows[0])
    _write_rows(path, rows)
    with pytest.raises(review.ReviewWorkflowError):
        _package(external, artifacts)

    other_path = external / _packet_name(2)
    other_rows = _read_rows(other_path)
    original[0], other_rows[0] = other_rows[0], original[0]
    _write_rows(path, original)
    _write_rows(other_path, other_rows)
    with pytest.raises(review.ReviewDecisionPackageError, match="packet assignment"):
        _package(external, artifacts)


def test_valid_reject_and_needs_correction_are_supported(
    package_work: tuple[Path, Path],
) -> None:
    external, artifacts = package_work
    path = external / _packet_name(1)
    rows = _read_rows(path)
    rows[0]["decision"] = "reject"
    rows[0]["reason_codes"] = ["wrong_track_span"]
    rows[1]["decision"] = "needs_correction"
    rows[1]["reason_codes"] = ["wrong_album_span"]
    _write_rows(path, rows)
    result = _package(external, artifacts)
    progress = result["review_progress"]
    assert progress["accepted"] == 3598
    assert progress["rejected"] == progress["needs_correction"] == 1
    assert progress["conflict"] == progress["pending"] == 0
    assert progress["raw_decision_counts"] == {
        "accept": 3598, "reject": 1, "needs_correction": 1,
    }


def test_existing_conflicting_evidence_is_never_overwritten(
    package_work: tuple[Path, Path],
) -> None:
    external, artifacts = package_work
    _package(external, artifacts)
    target = artifacts / "review" / "decisions" / _packet_name(1)
    target.write_bytes(b"conflicting evidence\n")
    with pytest.raises(review.ReviewDecisionPackageError, match="overwrite"):
        _package(external, artifacts)
    assert target.read_bytes() == b"conflicting evidence\n"


def test_source_identity_and_frozen_packet_drift_are_rejected(
    package_work: tuple[Path, Path],
) -> None:
    external, artifacts = package_work
    packet_path = artifacts / "review" / "packets" / "packet-01.jsonl"
    packet_path.write_bytes(packet_path.read_bytes() + b"{}\n")
    with pytest.raises(review.ReviewDecisionPackageError, match="frozen source packet"):
        _package(external, artifacts)

    shutil.copy2(review.DEFAULT_REVIEW_DIR / "packets" / "packet-01.jsonl", packet_path)
    config = artifacts / "generator_config.json"
    config.write_bytes(config.read_bytes().replace(b'"generator_version"', b'"different_version"', 1))
    with pytest.raises(review.ReviewSourceIdentityError):
        _package(external, artifacts)
