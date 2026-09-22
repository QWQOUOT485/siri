"""Offline tests for the provisional Stage B candidate corpus builder."""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_stage_b_candidate_corpus as candidate  # noqa: E402


CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")


def _variant_index(row: candidate.StageBCandidateRecord) -> int:
    return (int(row.candidate_id.rsplit("-", 1)[1]) - 1) % candidate.VARIANTS_PER_SOURCE_GROUP


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
    assert first_config["deterministic_reason_by_variant"] == {
        "0": "playback_control",
        "1": "playback_control",
        "2": "playback_control",
        "3": "playback_control",
        "4": "playback_control",
        "5": "unsupported_domain",
    }
    assert first_config["safety_reason_by_variant"] == {
        "0": "hostile_system",
        "1": "path_or_url",
        "2": "path_or_url",
        "3": "hostile_system",
        "4": "hostile_system",
        "5": "hostile_system",
    }
    assert len({row.candidate_id for row in first_rows}) == 3600
    assert len({row.source_group_id for row in first_rows}) == 600
    assert {row.generator_version for row in first_rows} == {"stage-b-candidate-generator-v2"}
    assert Counter(row.source_group_id for row in first_rows) == Counter(
        {f"source-group-{index:04d}": 6 for index in range(1, 601)}
    )


def test_all_deterministic_rows_use_their_variant_negative_reason() -> None:
    rows, _catalog = candidate.generate_candidate_records()
    deterministic_rows = [
        row for row in rows if row.provisional_ai_scope == "deterministic_only"
    ]

    assert len(deterministic_rows) == 300
    assert all(
        row.provisional_negative_reason
        == candidate.DETERMINISTIC_REASON_BY_VARIANT[_variant_index(row)]
        for row in deterministic_rows
    )
    assert sum(
        row.provisional_negative_reason != "playback_control"
        for row in deterministic_rows
        if _variant_index(row) < 5
    ) == 0
    assert sum(
        row.provisional_negative_reason != "unsupported_domain"
        for row in deterministic_rows
        if _variant_index(row) == 5
    ) == 0


def test_all_safety_rows_use_their_variant_negative_reason() -> None:
    rows, _catalog = candidate.generate_candidate_records()
    safety_rows = [row for row in rows if row.provisional_ai_scope == "safety_only"]

    assert len(safety_rows) == 240
    assert all(
        row.provisional_negative_reason
        == candidate.SAFETY_REASON_BY_VARIANT[_variant_index(row)]
        for row in safety_rows
    )
    assert sum(
        row.provisional_negative_reason != "hostile_system"
        for row in safety_rows
        if _variant_index(row) in {0, 3, 4, 5}
    ) == 0
    assert sum(
        row.provisional_negative_reason != "path_or_url"
        for row in safety_rows
        if _variant_index(row) in {1, 2}
    ) == 0


def test_language_surface_invariants_cover_the_full_candidate_pool() -> None:
    rows, _catalog = candidate.generate_candidate_records()
    mixed_rows = [row for row in rows if row.language_tag == "mixed"]
    english_rows = [row for row in rows if row.language_tag == "en"]

    assert len(mixed_rows) == 1140
    assert all(CJK_RE.search(row.utterance) for row in mixed_rows)
    assert all(ASCII_LETTER_RE.search(row.utterance) for row in mixed_rows)
    assert len(english_rows) == 792
    assert all(not CJK_RE.search(row.utterance) for row in english_rows)


def test_supported_chinese_play_rows_are_script_preserving() -> None:
    rows, _catalog = candidate.generate_candidate_records()
    chinese_play_rows = [
        row
        for row in rows
        if row.provisional_ai_scope == "supported"
        and row.provisional_expected.intent == "spotify_play_track"
        and row.language_tag in {"zh-Hant", "zh-Hans"}
    ]

    assert len(chinese_play_rows) == 864
    assert all(not ASCII_LETTER_RE.search(row.utterance) for row in chinese_play_rows)
    assert not hasattr(candidate, "ZH_HANT_PINYIN_SURFACE")
    assert not hasattr(candidate, "ZH_HANS_PINYIN_SURFACE")


def test_asr_noise_changes_at_most_one_present_entity_surface() -> None:
    rows, catalog = candidate.generate_candidate_records()
    entities = {entry["entity_key"]: entry for entry in catalog}
    noise_rows = [
        row
        for row in rows
        if row.provisional_ai_scope == "supported"
        and row.provisional_expected.intent == "spotify_play_track"
        and _variant_index(row) == 4
    ]

    assert len(noise_rows) == 300
    for row in noise_rows:
        entity_number = row.source_group_id.rsplit("-", 1)[1]
        entity = entities[f"synthetic-entity-{entity_number}"]
        changed = 0
        for field in ("track", "artist", "album"):
            span = getattr(row.provisional_expected, field)
            if span is not None and span.text != entity[field]:
                changed += 1
        assert changed <= 1, row.to_dict()


def test_quality_spot_check_fixture_has_all_review_relevant_surfaces() -> None:
    rows, _catalog = candidate.generate_candidate_records()
    spot_checks = {
        "zh-Hant play": next(
            row for row in rows
            if row.language_tag == "zh-Hant" and row.provisional_ai_scope == "supported"
            and row.provisional_expected.intent == "spotify_play_track"
        ),
        "zh-Hans play": next(
            row for row in rows
            if row.language_tag == "zh-Hans" and row.provisional_ai_scope == "supported"
            and row.provisional_expected.intent == "spotify_play_track"
        ),
        "mixed play": next(
            row for row in rows
            if row.language_tag == "mixed" and row.provisional_ai_scope == "supported"
            and row.provisional_expected.intent == "spotify_play_track"
        ),
        "English play": next(
            row for row in rows
            if row.language_tag == "en" and row.provisional_ai_scope == "supported"
            and row.provisional_expected.intent == "spotify_play_track"
        ),
        "zh-Hant semantic unknown": next(
            row for row in rows
            if row.language_tag == "zh-Hant" and row.provisional_ai_scope == "supported"
            and row.provisional_expected.intent == "unknown"
        ),
        "mixed semantic unknown": next(
            row for row in rows
            if row.language_tag == "mixed" and row.provisional_ai_scope == "supported"
            and row.provisional_expected.intent == "unknown"
        ),
        "deterministic-only": next(
            row for row in rows if row.provisional_ai_scope == "deterministic_only"
        ),
        "safety-only": next(
            row for row in rows if row.provisional_ai_scope == "safety_only"
        ),
        "ASR/homophone": next(
            row for row in rows if row.template_family == "play_hant_homophone"
        ),
    }

    assert len(spot_checks) == 9
    assert all(row.review_status == candidate.REVIEW_STATUS for row in spot_checks.values())
    assert all(row.utterance for row in spot_checks.values())
    assert all("stage_a" not in row.template_family for row in spot_checks.values())


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
    assert first_manifest["generator_version"] == "stage-b-candidate-generator-v2"
    assert first_manifest["exact_duplicate_count"] == 0
    assert first_manifest["same_group_near_duplicate_count"] == 0
    assert first_manifest["cross_group_near_duplicate_count"] == 0
    assert first_manifest["cross_group_duplicate_count"] == 0
    assert first_manifest["stage_a_leakage_count"] == 0
    assert first_manifest["deterministic_negative_reason_mismatch_count"] == 0
    assert first_manifest["safety_negative_reason_mismatch_count"] == 0
    assert first_manifest["mixed_without_cjk_count"] == 0
    assert first_manifest["mixed_without_ascii_letter_count"] == 0
    assert first_manifest["english_with_cjk_count"] == 0
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
