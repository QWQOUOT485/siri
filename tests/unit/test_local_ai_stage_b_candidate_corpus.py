"""Offline tests for the provisional Stage B candidate corpus builder."""

from __future__ import annotations

import ast
import inspect
import json
import sys
from collections import Counter
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_stage_b_candidate_corpus as candidate  # noqa: E402


def test_generation_never_reads_stage_a(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_stage_a(*_args: object, **_kwargs: object) -> set[str]:
        raise AssertionError("Stage A must not be read during candidate generation")

    monkeypatch.setattr(candidate.protocol, "load_stage_a_utterances", fail_stage_a)

    rows, catalog = candidate.generate_candidate_records()

    assert len(rows) == 3600
    assert len(catalog) == 600
    generation_source = inspect.getsource(candidate.generate_candidate_records).lower()
    assert "stage_a" not in generation_source
    assert "ai_intent_cases" not in generation_source


def test_generation_is_deterministic_and_ids_are_unique() -> None:
    first_rows, first_catalog = candidate.generate_candidate_records()
    second_rows, second_catalog = candidate.generate_candidate_records()

    assert [row.to_dict() for row in first_rows] == [row.to_dict() for row in second_rows]
    assert first_catalog == second_catalog
    assert candidate._candidate_corpus_hash(first_rows) == candidate._candidate_corpus_hash(second_rows)
    first_config = candidate._generator_config_payload()
    second_config = candidate._generator_config_payload()
    assert first_config == second_config
    assert len({row.candidate_id for row in first_rows}) == 3600
    assert len({row.source_group_id for row in first_rows}) == 600
    assert Counter(row.source_group_id for row in first_rows) == Counter(
        {f"source-group-{index:04d}": 6 for index in range(1, 601)}
    )


def test_candidate_schema_roundtrips_spans_and_keeps_review_pending() -> None:
    rows, _catalog = candidate.generate_candidate_records()

    for row in rows[::137]:
        restored = candidate.StageBCandidateRecord.from_mapping(row.to_dict())
        assert restored.to_dict() == row.to_dict()
        assert restored.review_status == candidate.REVIEW_STATUS
        expected = restored.provisional_expected
        for field in ("track", "artist", "album"):
            span = getattr(expected, field)
            if span is not None:
                assert restored.utterance[span.start : span.end] == span.text


def test_candidate_schema_rejects_authority_fields_and_non_pending_status() -> None:
    rows, _catalog = candidate.generate_candidate_records()
    payload = rows[0].to_dict()
    payload["spotify_uri"] = "spotify:track:forbidden"
    with pytest.raises(candidate.protocol.StageBSchemaError):
        candidate.StageBCandidateRecord.from_mapping(payload)

    payload = rows[0].to_dict()
    payload["review_status"] = "independently_reviewed"
    with pytest.raises(candidate.CandidateCorpusError):
        candidate.StageBCandidateRecord.from_mapping(payload)


def test_generator_has_no_external_runtime_or_stage_a_generation_dependency() -> None:
    tree = ast.parse(Path(candidate.__file__).read_text(encoding="utf-8"))
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
    source = Path(candidate.__file__).read_text(encoding="utf-8")
    assert "ai_intent_cases.json" not in source
    assert "spotify:track:" not in source


def test_artifact_manifest_review_queue_and_hashes_are_deterministic(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = candidate.build_candidate_artifacts(first_dir)
    second = candidate.build_candidate_artifacts(second_dir)
    first_manifest = first["manifest"]
    second_manifest = second["manifest"]

    assert first_manifest["manifest_sha256"] == second_manifest["manifest_sha256"]
    assert first_manifest["candidate_corpus_sha256"] == second_manifest["candidate_corpus_sha256"]
    assert first_manifest["entity_catalog_sha256"] == second_manifest["entity_catalog_sha256"]
    assert first_manifest["generator_config_sha256"] == second_manifest["generator_config_sha256"]
    assert first_manifest["review_queue_sha256"] == second_manifest["review_queue_sha256"]

    assert first_manifest["total_row_count"] == 3600
    assert first_manifest["scope_counts"] == {
        "supported_play": 1800,
        "supported_unknown": 1260,
        "deterministic_only": 300,
        "safety_only": 240,
    }
    assert first_manifest["ai_scope_counts"] == {
        "supported": 3060,
        "deterministic_only": 300,
        "safety_only": 240,
    }
    assert first_manifest["language_counts"] == {
        "zh-Hant": 1380,
        "zh-Hans": 288,
        "mixed": 1140,
        "en": 792,
    }
    assert first_manifest["supported_language_counts"] == {
        "zh-Hant": {"supported_total": 1200, "supported_play": 720, "supported_unknown": 480},
        "mixed": {"supported_total": 960, "supported_play": 540, "supported_unknown": 420},
    }
    assert first_manifest["slot_presence_counts"] == {
        "supported_play_rows": 1800,
        "artist_present": 1080,
        "artist_absent": 720,
        "album_present": 1080,
        "album_absent": 720,
        "artist_and_album_present": 720,
        "neither_optional_slot_present": 360,
    }
    assert first_manifest["source_group_count"] == 600
    assert first_manifest["template_family_count"] == 32
    assert first_manifest["exact_duplicate_count"] == 0
    assert first_manifest["same_group_near_duplicate_count"] == 0
    assert first_manifest["cross_group_near_duplicate_count"] == 0
    assert first_manifest["stage_a_leakage_count"] == 0
    assert first_manifest["review_status_counts"] == {candidate.REVIEW_STATUS: 3600}
    assert first_manifest["candidate_pool_split_status"] == "unsplit"
    assert first_manifest["final_split_assigned"] is False
    assert first_manifest["held_out_sealed"] is False
    assert first_manifest["FINAL_STAGE_B_CORPUS"] is False
    assert first_manifest["training_authorized"] is False
    assert first_manifest["model_compute_authorized"] is False
    assert first_manifest["semantic_memory_enabled"] is False
    assert first_manifest["local_ai_fallback_approved"] is False
    assert first["artifact_total_size_bytes"] < 50 * 1024 * 1024

    corpus_rows = [
        json.loads(line)
        for line in (first_dir / "candidate_corpus.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    review_rows = [
        json.loads(line)
        for line in (first_dir / "candidate_review_queue.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(corpus_rows) == len(review_rows) == 3600
    assert all(row["review_status"] == candidate.REVIEW_STATUS for row in corpus_rows)
    assert all(row["review_status"] == candidate.REVIEW_STATUS for row in review_rows)
    assert all("split" not in row for row in corpus_rows)
    assert all(set(row) == {"candidate_id", "record_sha256", "review_status", "review_reason"} for row in review_rows)
    assert all(row["review_reason"] is None for row in review_rows)
