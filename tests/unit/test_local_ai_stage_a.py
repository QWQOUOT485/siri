from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_benchmark_harness as harness  # noqa: E402
from local_ai_stage_a import classify_scope, language_slice, _skipped_observation  # noqa: E402
from local_ai_stage_a_adapters import (  # noqa: E402
    STAGE_A_IDENTITIES,
    _typed_choice_decision,
)


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


def test_batch_2a_identities_are_pinned_before_benchmark_loading():
    expected = {
        "kev": (
            "jaredpalmer/kev-0.5b",
            "e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c",
            "2679c20e6dde32fb3c4f97ecdad2e6e92bb88a06",
        ),
        "eve-rlcd": (
            "anthonym21/qwen3-0.6b-rlcd-decision",
            "57a179b7b1bedc80f65bf42ccda129dd1888272f",
            "b327ec5efb5fdbf8bfafa3b369720ac5f6434b05",
        ),
        "Verdict-open-jev": (
            "heman10x/rlcd-modernbert-151m",
            "30f15564821626ca5c1ad5b2638c4eb7078787dd",
            "8af2496eb63c7fa66d7d234e1f62629380030eb4",
        ),
    }

    for name, (model_id, repo_revision, model_revision) in expected.items():
        identity = STAGE_A_IDENTITIES[name]
        assert identity["model_id"] == model_id
        assert identity["repository_revision"] == repo_revision
        assert identity["model_revision"] == model_revision
        assert identity["hardware_alignment_status"] == "RX_9070_XT_BACKEND_BLOCKED"
        assert identity["route"] in {
            harness.AdapterRoute.DECODER_OPTION_SCORING.value,
            harness.AdapterRoute.ENCODER_CLASSIFICATION.value,
        }


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


def test_eligibility_skips_are_not_candidate_model_classifications():
    observation = _skipped_observation(
        {"id": "pause", "category": "playback_control", "input": "暫停"},
        "deterministic_only",
    )

    assert observation.inference_attempted is False
    assert observation.intent_ok is None
    assert observation.semantic_evaluated is False
    assert observation.slot_evidence_available is False
