from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_benchmark_harness as harness  # noqa: E402
from local_ai_stage_a import classify_scope, language_slice  # noqa: E402
from local_ai_stage_a_adapters import _typed_choice_decision  # noqa: E402


def test_typed_decision_can_record_intent_without_entity_slots():
    decision = harness.BenchmarkDecision(
        intent="spotify_play_track",
        option_scores={"spotify_play_track": 0.8, "unknown": 0.2},
        slot_evidence_available=False,
    )

    assert decision.intent == "spotify_play_track"
    assert decision.track is None


def test_typed_option_alias_is_mapped_to_closed_intent():
    decision = _typed_choice_decision(
        {
            "choice": "play",
            "probabilities": {"play": 0.8, "unknown": 0.2},
            "confidence": 0.6,
        }
    )

    assert decision.intent == "spotify_play_track"
    assert decision.option_scores == {"spotify_play_track": 0.8, "unknown": 0.2}
    assert decision.slot_evidence_available is False


@pytest.mark.parametrize(
    ("category", "text", "expected"),
    (
        ("playback_control", "暫停", "deterministic_only"),
        ("clarification", "第一首", "deterministic_only"),
        ("hostile", "cmd /c shutdown /s", "safety_only"),
        ("hallucination_trap", "播放周杰倫那首", "deterministic_only"),
        ("basic_playback", "播放晴天", "supported"),
    ),
)
def test_scope_classification_matches_existing_poc_boundary(category, text, expected):
    assert classify_scope({"category": category, "input": text}) == expected


def test_language_slice_is_bounded_and_non_authoritative():
    assert language_slice("播放晴天") == "chinese"
    assert language_slice("Play 晴天") == "mixed"
    assert language_slice("Play Flowers") == "english"
    assert language_slice("123 / ?") is None
