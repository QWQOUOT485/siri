from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_benchmark_harness as harness  # noqa: E402
from local_ai_model_storage import (  # noqa: E402
    DEFAULT_MODEL_ROOT,
    MODEL_ROOT_ENV,
    resolve_candidate_model_dir,
    resolve_model_root,
)
from local_ai_stage_a import (  # noqa: E402
    _load_failure_observation,
    _skipped_observation,
    build_adapter,
    classify_scope,
    language_slice,
    parse_args,
)
from local_ai_stage_a_adapters import (  # noqa: E402
    STAGE_A_IDENTITIES,
    StageAModelBlockedError,
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


def test_batch_2b_identities_are_pinned_before_benchmark_loading():
    expected = {
        "decider": (
            "Mapika/decider-2b",
            "c4daaac28af9fea95d627015cffa2dd5a5926ee6",
            "b37f7e1ba3fbc9238004cf531fabbee2619973fd",
        ),
        "open-jev-deberta-v3-large": (
            "com-kotobalabs/open-jev-deberta-v3-large",
            "bundled typed_decisions source at model revision",
            "19bf9a64815add579fbf6c907bef584d9277a8e4",
        ),
    }

    for name, (model_id, repo_revision, model_revision) in expected.items():
        identity = STAGE_A_IDENTITIES[name]
        assert identity["model_id"] == model_id
        assert identity["repository_revision"] == repo_revision
        assert identity["model_revision"] == model_revision
        assert identity["hardware_alignment_status"] == "RX_9070_XT_BACKEND_BLOCKED"

    assert STAGE_A_IDENTITIES["system-one-open"]["hardware_alignment_status"] == "MODEL_BLOCKED"
    assert "unavailable" in STAGE_A_IDENTITIES["system-one-open"]["quality_run_status"]


def test_common_model_root_prefers_cli_then_environment_then_portable_default(monkeypatch):
    monkeypatch.delenv(MODEL_ROOT_ENV, raising=False)
    assert resolve_model_root() == DEFAULT_MODEL_ROOT
    monkeypatch.setenv(MODEL_ROOT_ENV, r"D:\ai\ai")
    assert resolve_model_root() == Path(r"D:\ai\ai")
    assert resolve_model_root(r"E:\models") == Path(r"E:\models")


def test_candidate_model_root_layout_and_explicit_override():
    assert resolve_candidate_model_dir("decider", model_root=Path("models")) == Path("models/decider")
    assert resolve_candidate_model_dir(
        "open-jev-deberta-v3-large",
        model_root=Path("models"),
        override=Path(r"E:\custom\openjev"),
    ) == Path(r"E:\custom\openjev")


def test_runner_cli_model_root_resolves_new_candidates_without_production_config():
    args = parse_args(
        [
            "--candidate",
            "decider",
            "--model-root",
            r"D:\ai\ai",
            "--decider-source",
            "runtime/ai_poc/upstream-batch-2b/decider",
        ]
    )
    adapter, metadata = build_adapter(args)
    assert metadata["candidate_name"] == "decider"
    assert adapter._model_path == Path(r"D:\ai\ai\decider")


def test_blocked_candidate_is_not_treated_as_inference_failure():
    observation = _load_failure_observation(
        {
            "id": "blocked",
            "category": "basic_playback",
            "input": "播放晴天",
            "expected": {"intent": "spotify_play_track", "track": "晴天"},
        },
        "supported",
        "model_blocked",
    )
    assert observation.inference_attempted is False
    assert observation.error_type == "model_blocked"

    args = parse_args(["--candidate", "system-one-open"])
    adapter, metadata = build_adapter(args)
    assert metadata["hardware_alignment_status"] == "MODEL_BLOCKED"
    with pytest.raises(StageAModelBlockedError):
        adapter.prepare()

    result = harness.aggregate_observations(
        metadata,
        [
            observation,
            _skipped_observation(
                {"id": "gate", "category": "playback_control", "input": "暫停", "expected": {}},
                "deterministic_only",
            ),
        ],
        model_load_success=False,
    )
    assert result.play_recall is None
    assert result.unknown_recall is None


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
