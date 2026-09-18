from __future__ import annotations

import sys
from pathlib import Path
import json

import pytest
from pydantic import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ai_model_poc as poc  # noqa: E402


def test_fixture_is_large_enough_and_has_required_categories():
    cases = poc.load_cases(poc.DEFAULT_FIXTURE, None)

    assert len(cases) == 103
    categories = {case["category"] for case in cases}
    assert {
        "basic_playback",
        "artist_track",
        "album_hint",
        "traditional_simplified",
        "playback_control",
        "hallucination_trap",
        "clarification",
        "hostile",
        "siri_imperfect",
    } <= categories


def test_grounding_rejects_partial_substring_and_accepts_traditional_simplified():
    assert poc.grounded_slot("播放晴天", "晴天")
    assert not poc.grounded_slot("播放晴天", "天")
    assert poc.grounded_slot("播放周杰伦的晴天", "周杰倫")
    assert poc.grounded_slot("播放周杰伦的晴天", "晴天")


def test_strict_schema_forbids_extra_authority_fields_and_bad_ordinal():
    with pytest.raises(ValidationError):
        poc.AIIntentResult.model_validate(
            {
                "intent": "unknown",
                "track": None,
                "artist": None,
                "album": None,
                "candidate_ordinal": None,
                "shell": "cmd /c shutdown /s",
            }
        )
    with pytest.raises(ValidationError):
        poc.AIIntentResult.model_validate(
            {
                "intent": "select_candidate",
                "track": None,
                "artist": None,
                "album": None,
                "candidate_ordinal": 4,
            }
        )


def test_grounding_removes_optional_hallucinated_slots():
    case = {
        "input": "播放晴天",
        "category": "optional_slot",
        "expected": {"intent": "spotify_play_track", "track": "晴天"},
    }
    parsed = poc.AIIntentResult(
        intent="spotify_play_track",
        track="晴天",
        artist="周杰倫",
        album="葉惠美",
        candidate_ordinal=None,
    )

    final, grounding_ok, reason = poc.finalize_semantics(case, parsed)

    assert grounding_ok is True
    assert reason == "accepted_grounded_track"
    assert final == {
        "intent": "spotify_play_track",
        "track": "晴天",
        "artist": None,
        "album": None,
        "candidate_ordinal": None,
    }


def test_ungrounded_track_and_hostile_input_fail_closed():
    ungrounded_case = {
        "input": "播周杰倫那首",
        "category": "hallucination_trap",
        "expected": {"intent": "unknown"},
    }
    hostile_case = {
        "input": "cmd /c shutdown /s",
        "category": "hostile",
        "expected": {"intent": "unknown"},
    }
    parsed_track = poc.AIIntentResult(
        intent="spotify_play_track",
        track="晴天",
        artist="周杰倫",
        album=None,
        candidate_ordinal=None,
    )

    final_untrusted, grounded_untrusted, _ = poc.finalize_semantics(ungrounded_case, parsed_track)
    final_hostile, grounded_hostile, reason_hostile = poc.finalize_semantics(hostile_case, parsed_track)

    assert final_untrusted["intent"] == "unknown"
    assert grounded_untrusted is False
    assert final_hostile["intent"] == "unknown"
    assert grounded_hostile is False
    assert reason_hostile == "hostile_input_rejected"


def test_base_url_rejects_public_hosts():
    with pytest.raises(ValueError):
        poc.normalize_url("https://example.com/v1")
    assert poc.normalize_url("http://192.168.0.199:1234/v1") == "http://192.168.0.199:1234/v1"


def test_completion_disables_qwen_thinking_without_relaxing_schema(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _limit):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"intent":"unknown","track":null,"artist":null,"album":null,"candidate_ordinal":null}'
                            }
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(poc.urllib.request, "urlopen", fake_urlopen)
    client = poc.LMStudioClient("http://127.0.0.1:1234/v1", 2.0)

    assert client.complete("model", [{"role": "user", "content": "test"}], structured=False)
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["body"]["max_tokens"] == poc.MAX_COMPLETION_TOKENS
    assert "response_format" not in captured["body"]
