"""Offline final-v1 whole-group selection and pre-seal boundary tests."""

from __future__ import annotations

import ast
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import local_ai_stage_b_corpus as protocol  # noqa: E402
import local_ai_stage_b_final_selection as final  # noqa: E402
import local_ai_stage_b_independent_review as review  # noqa: E402


@pytest.fixture(scope="module")
def verified() -> final.VerifiedInputs:
    return final.load_verified_inputs()


@pytest.fixture(scope="module")
def groups(verified: final.VerifiedInputs) -> dict[str, final.SourceGroup]:
    return final._groups(verified.source)


@pytest.fixture(scope="module")
def assignment(groups: dict[str, final.SourceGroup]) -> dict[str, str]:
    return final.assign_groups(groups)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    path = tmp_path_factory.mktemp("stage-b-final-v1") / "final_v1"
    return path, final.build_final_artifacts(output_dir=path)


def _copy_frozen(tmp_path: Path) -> Path:
    path = tmp_path / "v6"
    shutil.copytree(review.DEFAULT_STAGE_B_ARTIFACT_DIR, path)
    return path


def test_frozen_source_and_complete_review_identities(verified: final.VerifiedInputs) -> None:
    assert dict(verified.source.identities) == dict(review.REVIEWED_SOURCE_IDENTITIES)
    assert verified.decision_manifest["decision_manifest_sha256"] == final.DECISION_MANIFEST_SHA256
    assert verified.review_progress["review_progress_sha256"] == final.REVIEW_PROGRESS_SHA256
    assert verified.review_progress["accepted"] == len(verified.decisions) == 3600
    assert verified.decision_manifest["reviewer_role_ids"] == ["gemini-3-8-high-v6-independent"]
    assert all(item["decision"] == "accept" for item in verified.decisions)


def test_missing_duplicate_and_nonaccepted_review_fail_closed(verified: final.VerifiedInputs) -> None:
    decisions = list(verified.decisions)
    candidate_ids = set(verified.source.rows_by_id)
    for invalid in (
        decisions[:-1],
        decisions[:-1] + [decisions[0]],
        decisions + [decisions[0]],
    ):
        with pytest.raises(final.FinalSelectionError, match="cover"):
            final._require_accepted_coverage(invalid, candidate_ids)
    for value in ("reject", "needs_correction", "conflict", "pending"):
        changed = [dict(decisions[0], decision=value), *decisions[1:]]
        with pytest.raises(final.FinalSelectionError, match="accepted"):
            final._require_accepted_coverage(changed, candidate_ids)


def test_source_groups_are_six_rows_and_class_homogeneous(groups: dict[str, final.SourceGroup]) -> None:
    assert len(groups) == 600
    assert all(len(group.rows) == 6 and {review._review_scope(row) for row in group.rows} == {group.class_key} for group in groups.values())
    assert {key: sum(group.class_key == key for group in groups.values()) for key in final.CLASS_KEYS} == {
        "supported_play": 300, "supported_unknown": 210,
        "deterministic_only": 50, "safety_only": 40,
    }


def test_broken_group_shape_and_homogeneity_fail(verified: final.VerifiedInputs) -> None:
    rows = list(verified.source.rows)
    with pytest.raises(final.FinalSelectionError, match="six-row"):
        final._groups(replace(verified.source, rows=tuple(rows[:-1])))
    changed = dict(rows[0], provisional_ai_scope="safety_only")
    with pytest.raises(final.FinalSelectionError, match="class-homogeneous"):
        final._groups(replace(verified.source, rows=(changed, *rows[1:])))


def test_whole_group_assignment_exact_counts_and_exclusion(
    groups: dict[str, final.SourceGroup], assignment: dict[str, str]
) -> None:
    assert len(assignment) == 600 and set(assignment) == set(groups)
    assert {state: list(assignment.values()).count(state) for state in ("train", "validation", "test", "excluded")} == {
        "train": 300, "validation": 100, "test": 100, "excluded": 100,
    }
    for split in protocol.SPLIT_NAMES:
        counts = {key: sum(groups[group_id].class_key == key for group_id, state in assignment.items() if state == split) for key in final.CLASS_KEYS}
        assert counts == final.GROUP_TARGETS[split]
        assert sum(counts.values()) * 6 == protocol.EXPECTED_SPLIT_COUNTS[split]["total"]
    assert {key: sum(groups[group_id].class_key == key for group_id, state in assignment.items() if state == "excluded") for key in final.CLASS_KEYS} == {
        "supported_play": 50, "supported_unknown": 30, "deterministic_only": 10, "safety_only": 10,
    }


def test_order_invariant_assignment_and_row_serialization(
    verified: final.VerifiedInputs, groups: dict[str, final.SourceGroup], assignment: dict[str, str]
) -> None:
    reversed_source = replace(verified.source, rows=tuple(reversed(verified.source.rows)))
    assert final.assign_groups(final._groups(reversed_source)) == assignment
    assert final.assign_groups(dict(reversed(list(groups.items())))) == assignment
    assert review.review_progress(tuple(reversed(verified.decisions))) == review.review_progress(verified.decisions)
    rows = [final._record(row) for row in groups["source-group-0001"].rows]
    assert final._jsonl_bytes(rows) == final._jsonl_bytes(list(reversed(rows)))


def test_authoritative_validator_stage_a_and_frozen_near_duplicate(
    built: tuple[Path, dict[str, object]]
) -> None:
    path, selection = built
    corpus_manifest = json.loads((path / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert corpus_manifest["total_row_count"] == 3000
    assert corpus_manifest["source_group_count"] == 500
    assert corpus_manifest["near_duplicate_policy"]["config_sha256"] == protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256
    assert selection["stage_a_sha256"] == protocol.EXPECTED_STAGE_A_SHA256
    assert selection["canonical_corpus_sha256"] == corpus_manifest["corpus_sha256"]
    assert selection["canonical_split_sha256"] == corpus_manifest["split_sha256"]


def test_held_out_frozen_gates_and_preseal_flags(built: tuple[Path, dict[str, object]]) -> None:
    _, selection = built
    gates = selection["held_out_language_gates"]
    for language in ("zh-Hant", "mixed"):
        assert gates[language]["supported_total"] >= 100
        assert gates[language]["supported_play"] >= 40
        assert gates[language]["supported_unknown"] >= 40
    slots = selection["held_out_optional_slots"]
    for key, minimum in protocol.OPTIONAL_SLOT_MINIMUMS.items():
        assert slots[key] >= minimum
    assert slots["artist_present_rows"] + slots["artist_absent_rows"] == 300
    assert slots["album_present_rows"] + slots["album_absent_rows"] == 300
    assert selection["final_split_assigned"] is True
    for key in ("held_out_sealed", "training_authorized", "model_compute_authorized", "semantic_memory_enabled", "local_ai_fallback_approved"):
        assert selection[key] is False


def test_repeated_complete_build_is_byte_identical_and_overwrite_safe(
    built: tuple[Path, dict[str, object]], tmp_path: Path
) -> None:
    path, selection = built
    other = tmp_path / "final_v1"
    assert final.build_final_artifacts(output_dir=path) == selection
    assert final.build_final_artifacts(output_dir=other) == selection
    assert {p.name: p.read_bytes() for p in path.iterdir()} == {p.name: p.read_bytes() for p in other.iterdir()}
    (other / "README.md").write_text("conflict", encoding="utf-8")
    with pytest.raises(final.FinalSelectionError, match="overwrite"):
        final.build_final_artifacts(output_dir=other)


def test_frozen_source_and_package_tampering_fail(tmp_path: Path) -> None:
    artifacts = _copy_frozen(tmp_path)
    source_path = artifacts / "candidate_corpus.jsonl"
    source_path.write_bytes(source_path.read_bytes().replace(b"candidate-00001", b"candidate-90001", 1))
    with pytest.raises(review.ReviewSourceIdentityError):
        final.load_verified_inputs(artifacts)
    shutil.copy2(review.DEFAULT_STAGE_B_ARTIFACT_DIR / "candidate_corpus.jsonl", source_path)
    manifest_path = artifacts / "review" / "decision_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["decision_manifest_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(final.FinalSelectionError, match="identity"):
        final.load_verified_inputs(artifacts)


def test_packaged_decision_file_and_progress_tampering_fail(tmp_path: Path) -> None:
    artifacts = _copy_frozen(tmp_path)
    decision_path = artifacts / "review" / "decisions" / "packet-01.decisions.jsonl"
    decision_path.write_bytes(decision_path.read_bytes().splitlines(keepends=True)[1:][0] + b"\n")
    with pytest.raises(final.FinalSelectionError):
        final.load_verified_inputs(artifacts)
    shutil.copy2(review.DEFAULT_REVIEW_DIR / "decisions" / "packet-01.decisions.jsonl", decision_path)
    progress_path = artifacts / "review" / "review_progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    progress["accepted"] = 3599
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    with pytest.raises(final.FinalSelectionError, match="identity"):
        final.load_verified_inputs(artifacts)


def test_near_duplicate_config_mutation_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mutated = replace(protocol.DEFAULT_NEAR_DUPLICATE_CONFIG, similarity_threshold=0.84)
    monkeypatch.setattr(protocol, "DEFAULT_NEAR_DUPLICATE_CONFIG", mutated)
    with pytest.raises(final.FinalSelectionError, match="near-duplicate"):
        final.build_final_artifacts(output_dir=tmp_path / "final_v1")


def test_cross_split_duplicate_and_near_duplicate_remain_fail_closed(
    verified: final.VerifiedInputs,
) -> None:
    row = next(
        row for row in verified.source.rows
        if row["provisional_ai_scope"] == "safety_only" and len(row["utterance"]) >= 28
    )
    original = final._record(row)
    duplicate = replace(original, case_id="synthetic-duplicate", source_group_id="synthetic-group")
    with pytest.raises(protocol.StageBLeakageError, match="duplicate"):
        protocol.validate_corpus({"train": [original], "test": [duplicate]}, stage_a_path=None)
    near = replace(duplicate, utterance=original.utterance + "測")
    assert protocol.near_duplicate_similarity(original.utterance, near.utterance) >= 0.85
    with pytest.raises(protocol.StageBLeakageError, match="near-duplicate"):
        protocol.validate_corpus({"train": [original], "test": [near]}, stage_a_path=None)


def test_stage_a_is_not_read_during_assignment(
    monkeypatch: pytest.MonkeyPatch, groups: dict[str, final.SourceGroup], assignment: dict[str, str]
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Stage A entered selection")

    monkeypatch.setattr(protocol, "load_stage_a_utterances", forbidden)
    assert final.assign_groups(groups) == assignment


def test_selection_module_has_no_runtime_or_model_dependencies() -> None:
    tree = ast.parse(Path(final.__file__).read_text(encoding="utf-8"))
    imports = {
        name.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for name in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not imports & {"app", "socket", "subprocess", "requests", "httpx", "spotify", "torch", "transformers", "win32api"}
