"""Offline tests for the Stage B corpus schema and protocol validator."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
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
    return {
        "case_id": case_id,
        "source_group_id": f"group_{case_id}",
        "utterance": f"Synthetic unknown request {case_id}",
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


def test_near_duplicate_policy_is_explicitly_deferred_without_an_arbitrary_threshold() -> None:
    result = corpus.inspect_near_duplicates([])
    assert result.implemented is False
    assert result.pairs == ()
    assert "future corpus-build" in result.reason
