"""Static invariants for the non-executing Stage B adaptation plan."""

from __future__ import annotations

import json
import re
from pathlib import Path


PLAN_PATH = Path(__file__).resolve().parents[2] / "docs" / "LOCAL_AI_STAGE_B_ADAPTATION_PLAN.md"


def _plan_text() -> str:
    return PLAN_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")


def _sample_record() -> dict[str, object]:
    match = re.search(r"```json\n(?P<body>\{.*?\})\n```", _plan_text(), re.DOTALL)
    assert match is not None, "the plan must contain its JSON example record"
    return json.loads(match.group("body"))


def test_stage_b_example_uses_immutable_original_utterance_spans() -> None:
    record = _sample_record()
    utterance = record["utterance"]
    assert isinstance(utterance, str)
    assert record["language_tag"] == "mixed"
    assert record["language_slice"] == "mixed"
    assert record["optional_slot_status"] == {"artist": "present", "album": "absent"}

    expected = record["expected"]
    assert isinstance(expected, dict)
    spans = []
    for field in ("track", "artist", "album"):
        span = expected[field]
        if field in ("artist", "album"):
            expected_status = "present" if span is not None else "absent"
            assert record["optional_slot_status"][field] == expected_status
        if span is None:
            continue
        assert isinstance(span, dict)
        start = span["start"]
        end = span["end"]
        text = span["text"]
        assert isinstance(start, int) and isinstance(end, int) and isinstance(text, str)
        assert start >= 0
        assert end > start
        assert end <= len(utterance)
        assert utterance[start:end] == text
        spans.append((start, end, field))

    assert (4, 14, "artist") in spans
    assert (17, 32, "track") in spans
    for previous, current in zip(sorted(spans), sorted(spans)[1:]):
        assert previous[1] <= current[0], f"overlapping example spans: {previous}, {current}"


def test_stage_b_plan_freezes_offset_language_and_slot_invariants() -> None:
    plan = _plan_text()
    normalized_plan = " ".join(plan.split())
    required_phrases = (
        "0-based",
        "end-exclusive",
        "Unicode Python `str` code-point indexing",
        'utterance[start:end] == span["text"]',
        "negative `start` or `end` values",
        "`end <= start`",
        "beyond `len(utterance)`",
        "text mismatch with `utterance[start:end]`",
        "reproduced from normalized text rather than the original stored utterance",
        "overlapping or otherwise impossible span structures",
        "`language_tag`: exactly one of `zh-Hant`, `zh-Hans`, `en`, or `mixed`",
        "at least **100 supported rows** with `language_tag=zh-Hant`",
        "at least **100 supported rows** with `language_tag=mixed`",
        "artist` present: at least **150 / 300**",
        "artist` absent but applicable: at least **100 / 300**",
        "album` present: at least **100 / 300**",
        "album` absent but applicable: at least **150 / 300**",
        "exactly one `present` or `absent` classification",
        "`artist_present_rows + artist_absent_rows == 300`",
        "`album_present_rows + album_absent_rows == 300`",
        "`optional_slot_status`",
        "no `N/A`, `ignored`, `excluded`, or `unscored` state",
        "missing or dual classification",
        "null-present",
        "non-null-absent",
        "partition sum not equal to 300",
        "`ceil(0.95 * actual_denominator)`",
        "must not be filtered, sampled out, excluded, or left unscored after",
        "presence recall",
        "exact-span accuracy when present",
        "absence specificity/correct-null rate",
        "combined result only as an additional summary",
    )
    for phrase in required_phrases:
        assert phrase in normalized_plan, f"missing frozen plan invariant: {phrase}"


def test_stage_b_implementation_evidence_uses_remote_pinned_commits() -> None:
    plan = _plan_text()
    assert "runtime/ai_poc/upstream" not in plan
    assert (
        "https://github.com/NandhaKishorM/laya/blob/"
        "42626c348753fbb17572a813127df2278a1ec527/"
        "laya/common.py#L45-L128"
    ) in plan
    assert (
        "https://github.com/Mapika/decider/blob/"
        "c4daaac28af9fea95d627015cffa2dd5a5926ee6/"
        "decider/model.py#L5-L24"
    ) in plan
    assert "NO STAGE B FINALIST FROM RELEASED STAGE A MODELS" in " ".join(plan.split())
    assert "Stage B test" in plan and "No diagnosis or tuning after seeing the test" in plan
    assert "LOCAL_AI_FALLBACK_APPROVED=false" in plan
