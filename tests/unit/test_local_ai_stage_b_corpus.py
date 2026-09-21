"""Offline tests for the Stage B corpus schema and protocol validator."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
NEAR_DUPLICATE_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "stage_b_near_duplicate_policy_cases.json"
)
EXPECTED_NEAR_DUPLICATE_FIXTURE_SHA256 = (
    "eadd304a4b6abfab262f2d4395edcd67d6eda9522b3020337517a73720dd6e85"
)
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_stage_b_corpus as corpus  # noqa: E402


def _positive_row(
    case_id: str = "synthetic_positive_001",
    *,
    artist: str | None = "Artist One",
    album: str | None = "Album One",
    language_tag: str = "en",
    source_group_id: str | None = None,
) -> dict[str, object]:
    artist_text = artist or ""
    album_text = album or ""
    pieces = ["Play"]
    if artist is not None:
        pieces.append(artist_text)
    pieces.append(f"Track {case_id}")
    if album is not None:
        pieces.append(album_text)
    utterance = " :: ".join(pieces)

    expected: dict[str, object] = {
        "intent": "spotify_play_track",
        "track": None,
        "artist": None,
        "album": None,
    }
    track_text = f"Track {case_id}"
    track_start = utterance.index(track_text)
    expected["track"] = {
        "text": track_text,
        "start": track_start,
        "end": track_start + len(track_text),
    }
    for field, value in (("artist", artist), ("album", album)):
        if value is not None:
            start = utterance.index(value)
            expected[field] = {"text": value, "start": start, "end": start + len(value)}

    return {
        "case_id": case_id,
        "source_group_id": source_group_id or f"group_{case_id}",
        "utterance": utterance,
        "language_tag": language_tag,
        "language_slice": {
            "zh-Hant": "chinese",
            "zh-Hans": "chinese",
            "en": "english",
            "mixed": "mixed",
        }[language_tag],
        "ai_scope": "supported",
        "expected": expected,
        "optional_slot_status": {
            "artist": "present" if artist is not None else "absent",
            "album": "present" if album is not None else "absent",
        },
        "negative_reason": None,
        "template_family": f"synthetic_template_{case_id}",
        "generator_version": "unit-test-v1",
    }


def _unknown_row(
    case_id: str,
    *,
    scope: str = "supported",
    language_tag: str = "en",
    negative_reason: str | None = "missing_track",
) -> dict[str, object]:
    synthetic_token = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
    return {
        "case_id": case_id,
        "source_group_id": f"group_{case_id}",
        "utterance": f"Synthetic unknown request {synthetic_token}",
        "language_tag": language_tag,
        "language_slice": {
            "zh-Hant": "chinese",
            "zh-Hans": "chinese",
            "en": "english",
            "mixed": "mixed",
        }[language_tag],
        "ai_scope": scope,
        "expected": {"intent": "unknown", "track": None, "artist": None, "album": None},
        "optional_slot_status": None,
        "negative_reason": negative_reason,
        "template_family": f"synthetic_template_{case_id}",
        "generator_version": "unit-test-v1",
    }


def _compact_splits() -> dict[str, list[dict[str, object]]]:
    return {
        "train": [
            _positive_row("synthetic_positive_001"),
            _unknown_row("synthetic_unknown_001"),
            _unknown_row(
                "synthetic_deterministic_001",
                scope="deterministic_only",
                negative_reason="playback_control",
            ),
        ],
        "validation": [_positive_row("synthetic_positive_002", artist=None)],
        "test": [_unknown_row("synthetic_unknown_002", scope="safety_only", negative_reason="hostile_system")],
    }


def _protocol_splits() -> dict[str, list[dict[str, object]]]:
    targets = corpus.EXPECTED_SPLIT_COUNTS
    splits: dict[str, list[dict[str, object]]] = {}
    for split in corpus.SPLIT_NAMES:
        rows: list[dict[str, object]] = []
        target = targets[split]
        for index in range(target["supported_play"]):
            if split == "test" and index < 50:
                language_tag = "zh-Hant"
            elif split == "test" and index < 100:
                language_tag = "mixed"
            else:
                language_tag = "en"
            rows.append(
                _positive_row(
                    f"{split}_play_{index:04d}",
                    artist=(f"Artist {split} {index}" if index % 2 == 0 else None),
                    album=(f"Album {split} {index}" if index % 2 == 0 else None),
                    language_tag=language_tag,
                )
            )
        for index in range(target["supported_unknown"]):
            if split == "test" and index < 50:
                language_tag = "zh-Hant"
            elif split == "test" and index < 100:
                language_tag = "mixed"
            else:
                language_tag = "en"
            rows.append(
                _unknown_row(
                    f"{split}_unknown_{index:04d}",
                    language_tag=language_tag,
                )
            )
        for index in range(target["deterministic_only"]):
            rows.append(
                _unknown_row(
                    f"{split}_deterministic_{index:04d}",
                    scope="deterministic_only",
                    negative_reason="playback_control",
                )
            )
        for index in range(target["safety_only"]):
            rows.append(
                _unknown_row(
                    f"{split}_safety_{index:04d}",
                    scope="safety_only",
                    negative_reason="hostile_system",
                )
            )
        splits[split] = rows
    return splits


def _assert_schema_error(row: dict[str, object]) -> None:
    with pytest.raises(corpus.StageBSchemaError):
        corpus.StageBRecord.from_mapping(row)


def test_compact_fixture_validates_and_exposes_manifest_counts() -> None:
    result = corpus.validate_corpus(_compact_splits())

    assert result.protocol_counts_enforced is False
    assert result.manifest["total_row_count"] == 5
    assert result.manifest["supported_play_count"] == 2
    assert result.manifest["supported_semantic_unknown_count"] == 1
    assert result.manifest["deterministic_only_count"] == 1
    assert result.manifest["safety_only_count"] == 1
    assert result.manifest["artist_present_count"] == 1
    assert result.manifest["artist_absent_count"] == 1
    assert result.manifest["album_present_count"] == 2
    assert result.manifest["album_absent_count"] == 0
    assert set(result.manifest["split_sha256"]) == set(corpus.SPLIT_NAMES)


def test_final_protocol_mode_accepts_only_the_frozen_synthetic_shape() -> None:
    result = corpus.validate_protocol_corpus(_protocol_splits())

    assert result.protocol_counts_enforced is True
    assert result.manifest["total_row_count"] == 3000
    assert result.manifest["per_split_row_counts"] == {
        "train": 1800,
        "validation": 600,
        "test": 600,
    }
    assert result.manifest["optional_slot_partition"] == {
        "supported_play_rows": 1500,
        "artist_present_rows": 750,
        "artist_absent_rows": 750,
        "album_present_rows": 750,
        "album_absent_rows": 750,
    }
    assert result.manifest["held_out_language_gates"] == {
        "zh-Hant": {"supported_total": 100, "supported_play": 50, "supported_unknown": 50},
        "mixed": {"supported_total": 100, "supported_play": 50, "supported_unknown": 50},
    }


def test_protocol_hash_is_independent_of_input_order_and_mapping_key_order() -> None:
    original = _protocol_splits()
    reordered = {
        split: [dict(reversed(list(row.items()))) for row in reversed(rows)]
        for split, rows in reversed(list(original.items()))
    }

    first = corpus.validate_protocol_corpus(original)
    second = corpus.validate_protocol_corpus(reordered)

    assert first.manifest_json() == second.manifest_json()
    assert first.manifest["corpus_sha256"] == second.manifest["corpus_sha256"]
    assert first.manifest["split_sha256"] == second.manifest["split_sha256"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("start", True),
        ("start", -1),
        ("end", 0),
        ("text", "wrong text"),
    ),
)
def test_span_validation_rejects_bad_offsets_and_text(field: str, value: object) -> None:
    row = _positive_row()
    track = row["expected"]["track"]
    assert isinstance(track, dict)
    track[field] = value
    _assert_schema_error(row)


def test_span_validation_rejects_empty_and_normalized_text_only_spans() -> None:
    empty = _positive_row()
    empty_track = empty["expected"]["track"]
    assert isinstance(empty_track, dict)
    empty_track["text"] = ""
    _assert_schema_error(empty)

    normalized = _positive_row()
    normalized["utterance"] = "Play Fullwidth Ａ"
    normalized["expected"] = {
        "intent": "spotify_play_track",
        "track": {"text": "A", "start": 14, "end": 15},
        "artist": None,
        "album": None,
    }
    normalized["optional_slot_status"] = {"artist": "absent", "album": "absent"}
    _assert_schema_error(normalized)


def test_span_validation_rejects_overlapping_spans() -> None:
    row = _positive_row(artist="Artist One", album=None)
    row["expected"]["artist"] = copy.deepcopy(row["expected"]["track"])
    _assert_schema_error(row)


def test_positive_requires_track_and_unknown_cannot_have_slots() -> None:
    missing_track = _positive_row()
    missing_track["expected"]["track"] = None
    _assert_schema_error(missing_track)

    unknown = _unknown_row("synthetic_unknown_slots")
    unknown["expected"]["artist"] = {"text": "Artist", "start": 9, "end": 15}
    _assert_schema_error(unknown)


def test_language_mapping_and_closed_schema_are_enforced() -> None:
    bad_mapping = _positive_row(language_tag="zh-Hant")
    bad_mapping["language_slice"] = "mixed"
    _assert_schema_error(bad_mapping)

    bad_tag = _positive_row()
    bad_tag["language_tag"] = "zh-Hant-TW"
    _assert_schema_error(bad_tag)

    extra = _positive_row()
    extra["unexpected"] = True
    _assert_schema_error(extra)


@pytest.mark.parametrize(
    ("status", "artist", "album"),
    (
        (None, "Artist One", "Album One"),
        ({"artist": "n/a", "album": "present"}, "Artist One", "Album One"),
        ({"artist": ["present", "absent"], "album": "present"}, "Artist One", "Album One"),
        ({"artist": "present", "album": "absent"}, None, "Album One"),
        ({"artist": "absent", "album": "absent"}, "Artist One", "Album One"),
        ({"artist": "present", "album": "present"}, "Artist One", None),
    ),
)
def test_optional_slot_status_is_closed_and_matches_nullability(
    status: object,
    artist: str | None,
    album: str | None,
) -> None:
    row = _positive_row(artist=artist, album=album)
    row["optional_slot_status"] = status
    _assert_schema_error(row)


def test_non_supported_rows_remain_unknown_and_outside_optional_partition() -> None:
    row = _unknown_row("deterministic_positive", scope="deterministic_only")
    row["expected"] = _positive_row("nested") ["expected"]
    row["optional_slot_status"] = {"artist": "absent", "album": "absent"}
    _assert_schema_error(row)


def test_forbidden_execution_authority_fields_are_rejected_without_echoing_values() -> None:
    row = _positive_row()
    row["spotify_uri"] = "spotify:track:secret"
    with pytest.raises(corpus.StageBSchemaError) as error:
        corpus.StageBRecord.from_mapping(row)
    assert "spotify:track:secret" not in str(error.value)


def test_duplicate_case_group_and_utterance_boundaries_are_rejected() -> None:
    duplicate_case = _compact_splits()
    duplicate_case["validation"][0]["case_id"] = duplicate_case["train"][0]["case_id"]
    with pytest.raises(corpus.StageBLeakageError):
        corpus.validate_corpus(duplicate_case)

    crossing_group = {
        "train": [_positive_row("group_a", source_group_id="shared")],
        "test": [_positive_row("group_b", source_group_id="shared")],
    }
    with pytest.raises(corpus.StageBLeakageError):
        corpus.validate_corpus(crossing_group)

    first_entity = _positive_row("entity_a")
    second_entity = copy.deepcopy(first_entity)
    second_entity["case_id"] = "entity_b"
    second_entity["source_group_id"] = "group_entity_b"
    second_entity["utterance"] = "Please " + first_entity["utterance"]
    second_entity["template_family"] = first_entity["template_family"]
    for field in ("track", "artist", "album"):
        span = second_entity["expected"][field]
        if span is not None:
            start = second_entity["utterance"].index(span["text"])
            span["start"] = start
            span["end"] = start + len(span["text"])
    with pytest.raises(corpus.StageBLeakageError):
        corpus.validate_corpus({"train": [first_entity], "test": [second_entity]})

    source_row = _positive_row("utterance_a")
    duplicate_row = copy.deepcopy(source_row)
    duplicate_row["case_id"] = "utterance_b"
    duplicate_row["source_group_id"] = "group_utterance_b"
    duplicate_row["template_family"] = "synthetic_template_utterance_b"
    crossing_utterance = {"train": [source_row], "test": [duplicate_row]}
    with pytest.raises(corpus.StageBLeakageError):
        corpus.validate_corpus(crossing_utterance)


def test_stage_a_identity_and_leakage_boundary_are_enforced() -> None:
    assert corpus.stage_a_identity() == {
        "case_count": 109,
        "sha256": corpus.EXPECTED_STAGE_A_SHA256,
    }

    row = {
        "case_id": "stage_a_leak",
        "source_group_id": "stage_a_leak_group",
        "utterance": "播放晴天",
        "language_tag": "zh-Hant",
        "language_slice": "chinese",
        "ai_scope": "supported",
        "expected": {
            "intent": "spotify_play_track",
            "track": {"text": "晴天", "start": 2, "end": 4},
            "artist": None,
            "album": None,
        },
        "optional_slot_status": {"artist": "absent", "album": "absent"},
        "negative_reason": None,
        "template_family": "stage_a_leak",
        "generator_version": "unit-test-v1",
    }
    with pytest.raises(corpus.StageBLeakageError):
        corpus.validate_corpus({"train": [row]})


def test_protocol_mode_rejects_wrong_counts_and_language_or_partition_minima() -> None:
    short = _protocol_splits()
    short["test"].pop()
    with pytest.raises(corpus.StageBProtocolError):
        corpus.validate_protocol_corpus(short)

    wrong_language = _protocol_splits()
    for row in wrong_language["test"]:
        if row["ai_scope"] == "supported":
            row["language_tag"] = "en"
            row["language_slice"] = "english"
    with pytest.raises(corpus.StageBProtocolError):
        corpus.validate_protocol_corpus(wrong_language)

    below_optional_minimum = _protocol_splits()
    changed = 0
    for row in below_optional_minimum["test"]:
        if (
            row["ai_scope"] == "supported"
            and row["expected"]["intent"] == "spotify_play_track"
            and row["optional_slot_status"]["artist"] == "present"
        ):
            row["expected"]["artist"] = None
            row["optional_slot_status"]["artist"] = "absent"
            changed += 1
            if changed == 51:
                break
    with pytest.raises(corpus.StageBProtocolError):
        corpus.validate_protocol_corpus(below_optional_minimum)


def test_optional_partition_and_pass_count_helpers_are_frozen() -> None:
    with pytest.raises(corpus.StageBProtocolError):
        corpus.optional_slot_partition(
            [corpus.StageBRecord.from_mapping(_positive_row("only_one"))],
            require_protocol_partition=True,
        )
    assert corpus.required_pass_count(150) == 143
    assert corpus.required_pass_count(100) == 95
    assert corpus.required_pass_count(170) == 162
    assert corpus.required_pass_count(130) == 124


def test_local_path_boundary_rejects_network_device_and_uri_forms_before_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("rejected path reached file I/O")

    monkeypatch.setattr(Path, "read_text", fail_read)
    rejected = (
        r"\\server\share\file.json",
        "//server/share/file.json",
        r"\\.\pipe\stage-b",
        r"\\?\C:\stage-b.json",
        r"\\?\UNC\server\share\stage-b.json",
        "file://C:/stage-b.json",
        "http://example.invalid/stage-b.json",
        "https://example.invalid/stage-b.json",
        "custom+v1://host/stage-b.json",
    )
    for path in rejected:
        with pytest.raises(corpus.StageBPathError) as error:
            corpus.load_split_records(path)
        assert str(error.value) == "split_path must be a local filesystem path"
        with pytest.raises(corpus.StageBPathError):
            corpus.load_stage_a_utterances(path)
        with pytest.raises(corpus.StageBPathError):
            corpus.stage_a_identity(path)


def test_validate_corpus_paths_validates_all_paths_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safe_path = tmp_path / "safe.json"
    safe_path.write_text(json.dumps([_unknown_row("safe")]), encoding="utf-8")

    def fail_read(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("a safe path was read before all paths were checked")

    monkeypatch.setattr(Path, "read_text", fail_read)
    with pytest.raises(corpus.StageBPathError):
        corpus.validate_corpus_paths(
            {"train": safe_path, "test": r"\\server\share\unsafe.json"},
            stage_a_path=None,
        )


def test_ordinary_local_path_remains_supported(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    path.write_text(json.dumps([_unknown_row("local_path")]), encoding="utf-8")

    records = corpus.load_split_records(path)

    assert len(records) == 1
    assert records[0].case_id == "local_path"


def test_direct_stage_b_record_cannot_bypass_sensitive_structured_value_scan() -> None:
    uri = "https://evil.example/track"
    utterance = f"Play {uri}"
    expected = corpus.StageBExpected(
        intent="spotify_play_track",
        track=corpus.StageBSpan(uri, 5, 5 + len(uri)),
        artist=None,
        album=None,
    )
    direct_kwargs = {
        "case_id": "direct_sensitive",
        "source_group_id": "direct_sensitive_group",
        "utterance": utterance,
        "language_tag": "en",
        "language_slice": "english",
        "ai_scope": "supported",
        "expected": expected,
        "optional_slot_status": {"artist": "absent", "album": "absent"},
        "negative_reason": None,
        "template_family": "direct_sensitive",
        "generator_version": "unit-test-v1",
    }
    with pytest.raises(corpus.StageBSchemaError):
        corpus.StageBRecord(**direct_kwargs)

    mapping = _positive_row("mapping_sensitive", artist=None, album=None)
    mapping["utterance"] = utterance
    mapping["expected"] = {
        "intent": "spotify_play_track",
        "track": {"text": uri, "start": 5, "end": 5 + len(uri)},
        "artist": None,
        "album": None,
    }
    with pytest.raises(corpus.StageBSchemaError):
        corpus.StageBRecord.from_mapping(mapping)


def test_direct_stage_b_record_acceptance_matches_mapping_and_freezes_slot_status() -> None:
    row = _positive_row("direct_valid")
    parsed = corpus.StageBRecord.from_mapping(row)
    external_status = {"artist": "present", "album": "present"}
    direct = corpus.StageBRecord(
        case_id=parsed.case_id,
        source_group_id=parsed.source_group_id,
        utterance=parsed.utterance,
        language_tag=parsed.language_tag,
        language_slice=parsed.language_slice,
        ai_scope=parsed.ai_scope,
        expected=parsed.expected,
        optional_slot_status=external_status,
        negative_reason=parsed.negative_reason,
        template_family=parsed.template_family,
        generator_version=parsed.generator_version,
    )
    external_status["artist"] = "absent"

    mapping_result = corpus.validate_corpus({"train": [row]}, stage_a_path=None)
    direct_result = corpus.validate_corpus({"train": [direct]}, stage_a_path=None)

    assert direct.optional_slot_status["artist"] == "present"
    with pytest.raises(TypeError):
        direct.optional_slot_status["artist"] = "absent"
    assert direct_result.manifest_json() == mapping_result.manifest_json()


def test_near_duplicate_policy_fixture_is_frozen_and_uses_no_stage_a_rows() -> None:
    payload = json.loads(NEAR_DUPLICATE_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert payload["fixture_id"] == "stage_b_near_duplicate_policy_cases_v1"
    assert payload["source"] == "synthetic_non_stage_a_policy_calibration"
    assert payload["stage_a_inclusion"] == "none"
    assert payload["training_use"] == "forbidden"
    assert corpus._sha256_json(payload) == EXPECTED_NEAR_DUPLICATE_FIXTURE_SHA256
    stage_a_utterances = corpus.load_stage_a_utterances()
    fixture_texts = {
        pair[field]
        for pair in payload["pairs"]
        for field in ("left_text", "right_text")
    }
    assert all(
        corpus.canonicalize_for_comparison(text) not in stage_a_utterances
        for text in fixture_texts
    )

    for pair in payload["pairs"]:
        assert corpus.classify_near_duplicate(
            pair["left_text"],
            pair["right_text"],
        ) == pair["expected_relation"]


def test_near_duplicate_policy_is_order_invariant_and_manifest_serialized() -> None:
    left = _unknown_row("policy_left")
    right = _unknown_row("policy_right")
    left["utterance"] = "Play the Example Band Hypothetical Horizon"
    right["utterance"] = "Play the Example Band Hypothetical Horiz0n"
    records = [
        corpus.StageBRecord.from_mapping(left),
        corpus.StageBRecord.from_mapping(right),
    ]

    first = corpus.inspect_near_duplicates(records)
    second = corpus.inspect_near_duplicates(list(reversed(records)))

    assert first.implemented is True
    assert first.to_dict() == second.to_dict()
    assert first.pairs == (("policy_left", "policy_right"),)
    assert first.comparisons[0].relation == "near_duplicate"
    assert first.config_sha256 == corpus.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256

    result = corpus.validate_corpus(
        {"train": [_unknown_row("manifest_only")]},
        stage_a_path=None,
    )
    policy = result.manifest["near_duplicate_policy"]
    assert policy["algorithm"] == "char_ngram_jaccard_exact_v1"
    assert policy["ngram_size"] == 3
    assert policy["similarity_threshold"] == 0.85
    assert policy["config_sha256"] == corpus.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256

    changed = replace(
        corpus.DEFAULT_NEAR_DUPLICATE_CONFIG,
        similarity_threshold=0.86,
    )
    assert changed.config_sha256 != corpus.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256


def test_near_duplicate_policy_rejects_only_cross_split_pairs() -> None:
    left = _unknown_row("cross_split_left")
    right = _unknown_row("cross_split_right")
    left["utterance"] = "Play the Example Band Hypothetical Horizon"
    right["utterance"] = "Play the Example Band Hypothetical Horiz0n"

    with pytest.raises(corpus.StageBLeakageError, match="near-duplicate"):
        corpus.validate_corpus(
            {"train": [left], "test": [right]},
            stage_a_path=None,
        )

    same_split = corpus.validate_corpus(
        {"train": [left, right]},
        stage_a_path=None,
    )
    assert same_split.manifest["total_row_count"] == 2


def test_provenance_manifest_is_sanitized_and_derived_from_validation_identity() -> None:
    result = corpus.validate_corpus(
        {"train": [_unknown_row("provenance_only")]},
        stage_a_path=None,
    )

    provenance = corpus.build_provenance_manifest(
        result,
        corpus_protocol_version="stage-b-corpus-build-v1",
        generator_version="synthetic-policy-v1",
        generation_source="synthetic_policy_fixture",
        reviewer_role_id="role:independent-reviewer",
        review_status="independently_reviewed",
        review_timestamp_policy="opaque review record id; no personal identity",
        split_assignment_stage="group-aware-pre-seal",
        validation_tool_version="local_ai_stage_b_corpus@unit-test",
    )

    assert provenance["canonical_corpus_sha256"] == result.manifest["corpus_sha256"]
    assert provenance["final_split_sha256"] == result.manifest["split_sha256"]
    assert provenance["near_duplicate_config_sha256"] == (
        corpus.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256
    )
    assert len(provenance["provenance_sha256"]) == 64

    with pytest.raises(corpus.StageBSchemaError):
        corpus.build_provenance_manifest(
            result,
            corpus_protocol_version="stage-b-corpus-build-v1",
            generator_version="synthetic-policy-v1",
            generation_source="https://private.example/log",
            reviewer_role_id=None,
            review_status="pending",
            review_timestamp_policy="opaque review record id",
            split_assignment_stage="group-aware-pre-seal",
            validation_tool_version="local_ai_stage_b_corpus@unit-test",
        )


def test_near_duplicate_policy_has_no_external_runtime_dependencies() -> None:
    module = ast.parse(Path(corpus.__file__).read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        alias.name.split(".", 1)[0]
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        for alias in node.names
    )
    assert imported_roots.isdisjoint(
        {"requests", "httpx", "socket", "subprocess", "torch", "transformers"}
    )
