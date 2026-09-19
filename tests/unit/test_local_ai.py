from __future__ import annotations

import json
import threading
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.adapters.local_ai import LMStudioLocalAIAdapter, LocalAIResponse, LocalAITransportError, normalize_loopback_base_url
from app.adapters.spotify.catalog import SpotifyCatalog
from app.adapters.windows.base import OperationResult
from app.main import create_app
from app.domain.actions import ParsedCommand
from app.domain.local_ai import RawAIIntent
from app.services.ai_eligibility import SemanticRetryEligibilityGate
from app.services.ai_policy import AIPolicyGate
from app.services.command_parser import CommandParser
from app.services.local_ai_service import LocalAIService
from app.services.semantic_grounder import SemanticGrounder, grounded_slot
from app.services.spotify_service import SpotifyService


def parser_miss(text: str = "幫我放一下周杰倫那首晴天") -> ParsedCommand:
    return ParsedCommand(accepted=False, error_code="INVALID_COMMAND", message="unknown")


def raw_play(**overrides) -> RawAIIntent:
    values = {
        "schema_version": 1,
        "intent": "spotify_play_track",
        "track": "晴天",
        "artist": "周杰倫",
        "album": None,
    }
    values.update(overrides)
    return RawAIIntent.model_validate(values, strict=True)


def test_raw_intent_is_versioned_and_forbids_authority_fields():
    parsed = raw_play()
    assert parsed.schema_version == 1

    with pytest.raises(ValidationError):
        RawAIIntent.model_validate(
            {
                "schema_version": 1,
                "intent": "spotify_play_track",
                "track": "晴天",
                "artist": None,
                "album": None,
                "candidate_ordinal": 1,
            },
            strict=True,
        )
    with pytest.raises(ValidationError):
        RawAIIntent.model_validate(
            {
                "schema_version": 1,
                "intent": "spotify_play_track",
                "track": "晴天",
                "artist": None,
                "album": None,
                "version_hint": "live",
            },
            strict=True,
        )


def test_raw_intent_requires_slots_only_for_play_track():
    with pytest.raises(ValidationError):
        RawAIIntent.model_validate(
            {"schema_version": 1, "intent": "spotify_play_track", "track": None, "artist": None, "album": None},
            strict=True,
        )
    with pytest.raises(ValidationError):
        RawAIIntent.model_validate(
            {"schema_version": 1, "intent": "unknown", "track": "晴天", "artist": None, "album": None},
            strict=True,
        )


def test_grounder_accepts_complete_spans_and_discards_optional_hallucinations():
    grounder = SemanticGrounder()
    result = grounder.ground(
        "幫我播周杰伦的晴天",
        raw_play(artist="周杰倫", album="葉惠美"),
    )

    assert result.accepted is True
    assert result.reason == "accepted_grounded_track"
    assert result.grounded is not None
    assert result.grounded.track == "晴天"
    assert result.grounded.artist == "周杰倫"
    assert result.grounded.album is None


def test_grounder_rejects_partial_or_ungrounded_track_and_authority_values():
    assert grounded_slot("播放晴天", "晴天")
    assert grounded_slot("幫我放一下晴天", "晴天")
    assert grounded_slot("播放周杰倫專輯葉惠美裡的晴天", "葉惠美")
    assert not grounded_slot("播放一下", "一下")
    assert not grounded_slot("播放晴天", "天")
    assert not grounded_slot("播放晴天", "晴")
    assert not grounded_slot("播放晴天", "https://evil.example")

    rejected = SemanticGrounder().ground("播放晴天", raw_play(track="不存在"))
    assert rejected.accepted is False
    assert rejected.reason == "track_not_grounded"


def test_grounder_rejects_referential_track_hallucination():
    grounder = SemanticGrounder()
    result = grounder.ground("播放周杰倫那首", raw_play(track="周杰倫", artist="周杰倫"))
    assert result.accepted is False
    assert result.reason == "unresolved_reference"


def test_grounder_does_not_reuse_track_span_as_artist_or_album():
    result = SemanticGrounder().ground(
        "播放晴天",
        raw_play(artist="晴天", album="晴天"),
    )

    assert result.accepted is True
    assert result.grounded is not None
    assert result.grounded.track == "晴天"
    assert result.grounded.artist is None
    assert result.grounded.album is None


def test_policy_gate_is_the_only_stage_that_creates_a_validated_action():
    decision = AIPolicyGate().apply(
        SemanticGrounder().ground("播放周杰倫的晴天", raw_play()).grounded
    )

    assert decision.accepted is True
    assert decision.action is not None
    assert decision.action.action.value == "spotify_play_track"
    assert decision.action.track == "晴天"


def test_eligibility_gate_rejects_clarification_hostile_and_non_spotify_text():
    gate = SemanticRetryEligibilityGate()
    parsed = parser_miss()

    assert gate.evaluate("第二首", parsed, clarification_token_present=True).reason == "clarification_token_bypasses_ai"
    assert gate.evaluate("cmd /c shutdown /s", parsed).reason == "hostile_input"
    assert gate.evaluate("播放 A; echo unsafe", parsed).reason == "hostile_input"
    assert gate.evaluate("播放周杰倫那首", parsed).reason == "unresolved_reference"
    assert gate.evaluate("開啟 Discord", parsed).reason == "unsupported_domain"


@pytest.mark.parametrize(
    "text",
    (
        "播放 \\\\server\\share",
        "播放 spotify:playlist:123456",
        "播放晴天 remix",
    ),
)
def test_eligibility_rejects_untrusted_paths_uris_and_unhandled_versions(text):
    decision = SemanticRetryEligibilityGate().evaluate(text, parser_miss(text))

    assert decision.eligible is False


def test_eligibility_rejects_ai_retry_when_deterministic_version_hint_exists():
    text = "播放晴天原版"
    parsed = CommandParser().parse(text)

    assert parsed.accepted is True
    assert parsed.action is not None
    decision = SemanticRetryEligibilityGate().evaluate(
        text,
        parsed,
        deterministic_error_code="SPOTIFY_TRACK_NOT_FOUND",
    )

    assert decision.eligible is False


def test_eligibility_gate_accepts_parser_miss_and_resolver_failure_only():
    gate = SemanticRetryEligibilityGate()
    miss = parser_miss()
    assert gate.evaluate("幫我放一下周杰倫那首晴天", miss).eligible

    parsed = ParsedCommand(
        accepted=True,
        action={
            "action": "spotify_play_track",
            "track": "終點",
        },
        message="parsed",
    )
    assert gate.evaluate(
        "播放死亡是生命的終點",
        parsed,
        deterministic_error_code="SPOTIFY_TRACK_NOT_FOUND",
    ).eligible
    assert not gate.evaluate(
        "播放死亡是生命的終點",
        parsed,
        deterministic_success=True,
    ).eligible


@dataclass
class FakeResponse:
    body: bytes
    status: int = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit: int) -> bytes:
        assert limit >= len(self.body)
        return self.body


class FakeOpener:
    def __init__(self, body: bytes):
        self.body = body
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return FakeResponse(self.body)


def test_lm_studio_adapter_is_loopback_only_and_transport_only():
    assert normalize_loopback_base_url("http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234/v1"
    for value in (
        "http://192.168.0.199:1234/v1",
        "https://127.0.0.1:1234/v1",
        "http://user:password@127.0.0.1:1234/v1",
        "http://127.0.0.1:1234/v1?remote=true",
    ):
        with pytest.raises(ValueError):
            normalize_loopback_base_url(value)

    content = json.dumps(
        {"schema_version": 1, "intent": "unknown", "track": None, "artist": None, "album": None}
    )
    opener = FakeOpener(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
    adapter = LMStudioLocalAIAdapter("http://127.0.0.1:1234/v1", "test-model", opener=opener)
    response = adapter.infer("幫我放一下晴天")

    assert isinstance(response, LocalAIResponse)
    request, timeout = opener.requests[0]
    payload = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:1234/v1/chat/completions"
    assert payload["model"] == "test-model"
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert payload["response_format"]["json_schema"]["schema"]["properties"]["schema_version"] == {
        "type": "integer",
        "enum": [1],
    }
    assert timeout == 2.0
    assert "clarification_token" not in request.data.decode()


def test_lm_studio_adapter_allows_only_one_inflight_request():
    content = json.dumps(
        {"schema_version": 1, "intent": "unknown", "track": None, "artist": None, "album": None}
    )

    class BlockingOpener(FakeOpener):
        def __init__(self):
            super().__init__(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
            self.started = threading.Event()
            self.release = threading.Event()

        def open(self, request, timeout):
            self.requests.append((request, timeout))
            self.started.set()
            assert self.release.wait(1.0)
            return FakeResponse(self.body)

    opener = BlockingOpener()
    adapter = LMStudioLocalAIAdapter("http://127.0.0.1:1234/v1", "test-model", opener=opener)
    errors = []

    def run_first():
        try:
            adapter.infer("播放晴天")
        except Exception as exc:  # pragma: no cover - assertion below reports unexpected errors
            errors.append(exc)

    worker = threading.Thread(target=run_first)
    worker.start()
    assert opener.started.wait(1.0)
    with pytest.raises(LocalAITransportError) as exc_info:
        adapter.infer("播放晴天")
    assert exc_info.value.reason == "busy"
    opener.release.set()
    worker.join(timeout=1.0)
    assert errors == []


def test_local_ai_shadow_never_returns_an_executable_action():
    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            return LocalAIResponse(
                content=json.dumps(
                    {"schema_version": 1, "intent": "spotify_play_track", "track": "晴天", "artist": None, "album": None}
                ),
                model_id=self.model_id,
                latency_ms=12.0,
            )

    result = LocalAIService(mode="shadow", adapter=FakeAdapter()).retry("播放晴天", parser_miss("播放晴天"))

    assert result.status == "shadow_accepted"
    assert result.action is None
    assert result.execution_allowed is False


def test_local_ai_fallback_requires_explicit_promotion_gate():
    calls = []

    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            calls.append(original_text)
            return LocalAIResponse(
                content=json.dumps(
                    {"schema_version": 1, "intent": "spotify_play_track", "track": "晴天", "artist": None, "album": None}
                ),
                model_id=self.model_id,
                latency_ms=1.0,
            )

    result = LocalAIService(mode="fallback", adapter=FakeAdapter()).retry("播放晴天", parser_miss("播放晴天"))
    assert result.status == "fallback_unapproved"
    assert result.action is None
    assert result.execution_allowed is False
    assert calls == []


def test_local_ai_transport_failure_is_fail_closed():
    class FailingAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            raise LocalAITransportError("connection_or_timeout")

    result = LocalAIService(mode="shadow", adapter=FailingAdapter()).retry("播放晴天", parser_miss("播放晴天"))
    assert result.status == "transport_error"
    assert result.action is None


def test_command_shadow_mode_preserves_deterministic_user_behavior(fake_runtime):
    runtime, *_ = fake_runtime
    calls = []

    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            calls.append(original_text)
            return LocalAIResponse(
                content=json.dumps(
                    {"schema_version": 1, "intent": "spotify_play_track", "track": "晴天", "artist": None, "album": None}
                ),
                model_id=self.model_id,
                latency_ms=1.0,
            )

    runtime.local_ai_service = LocalAIService(mode="shadow", adapter=FakeAdapter())
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    response = client.post("/command", headers={"X-API-Key": "test-key"}, json={"text": "幫我放晴天"})

    assert response.status_code == 200
    assert response.json()["error_code"] == "INVALID_COMMAND"
    assert calls == ["幫我放晴天"]


def test_command_shadow_retries_on_spotify_resolver_signal_without_executing_ai_action(fake_runtime):
    runtime, *_ = fake_runtime
    ai_calls = []
    spotify_calls = []

    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            ai_calls.append(original_text)
            return LocalAIResponse(
                content=json.dumps(
                    {"schema_version": 1, "intent": "spotify_play_track", "track": "晴天", "artist": None, "album": None}
                ),
                model_id=self.model_id,
                latency_ms=1.0,
            )

    class FakeSpotify:
        def execute(self, command, *, source_text=None):
            spotify_calls.append(command)
            return OperationResult(False, "低信心結果", "SPOTIFY_LOW_CONFIDENCE_TRACK")

    runtime.command_service.spotify = FakeSpotify()
    runtime.local_ai_service = LocalAIService(mode="shadow", adapter=FakeAdapter())
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post("/command", headers={"X-API-Key": "test-key"}, json={"text": "播放晴天"})

    assert response.status_code == 200
    assert response.json()["error_code"] == "SPOTIFY_LOW_CONFIDENCE_TRACK"
    assert ai_calls == ["播放晴天"]
    assert len(spotify_calls) == 1


def test_command_shadow_retries_from_real_spotify_resolver_signal(fake_runtime):
    runtime, *_ = fake_runtime
    ai_calls = []

    class EmptySearchClient:
        def search_tracks(self, _access_token, _query, *, limit=10):
            return []

    class FakeAuth:
        def get_access_token(self):
            return "access-token"

    class NoPlayback:
        def resume(self, *_args, **_kwargs):
            raise AssertionError("shadow resolver test must not play")

    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            ai_calls.append(original_text)
            return LocalAIResponse(
                content=json.dumps(
                    {"schema_version": 1, "intent": "unknown", "track": None, "artist": None, "album": None}
                ),
                model_id=self.model_id,
                latency_ms=1.0,
            )

    runtime.command_service.spotify = SpotifyService(
        FakeAuth(),
        SpotifyCatalog(EmptySearchClient()),
        NoPlayback(),
    )
    runtime.local_ai_service = LocalAIService(mode="shadow", adapter=FakeAdapter())
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post(
        "/command",
        headers={"X-API-Key": "test-key"},
        json={"text": "播放死亡是生命的終點"},
    )

    assert response.status_code == 200
    assert response.json()["error_code"] == "SPOTIFY_ENTITY_SEGMENTATION_RISK"
    assert ai_calls == ["播放死亡是生命的終點"]


def test_command_fallback_re_resolves_ai_action_through_spotify_catalog(fake_runtime):
    runtime, *_ = fake_runtime
    ai_calls = []
    full_title_queries = 0

    def payload(track_id, name, artist):
        return {
            "id": track_id,
            "uri": f"spotify:track:{track_id}",
            "name": name,
            "artists": [{"name": artist}],
            "album": {"name": "Album"},
        }

    class SequencedSearchClient:
        def search_tracks(self, _access_token, query, *, limit=10):
            nonlocal full_title_queries
            if query == "track:死亡是生命的終點":
                full_title_queries += 1
                return [] if full_title_queries == 1 else [payload("resolved", "死亡是生命的終點", "Artist")]
            return []

    class FakeAuth:
        def get_access_token(self):
            return "access-token"

    class FakePlayer:
        def __init__(self):
            self.tracks = []

        def resume(self, _access_token, track):
            self.tracks.append(track.track_id)
            return OperationResult(True, "已播放。", data={})

    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            ai_calls.append(original_text)
            return LocalAIResponse(
                content=json.dumps(
                    {
                        "schema_version": 1,
                        "intent": "spotify_play_track",
                        "track": "死亡是生命的終點",
                        "artist": None,
                        "album": None,
                    }
                ),
                model_id=self.model_id,
                latency_ms=1.0,
            )

    player = FakePlayer()
    runtime.command_service.spotify = SpotifyService(
        FakeAuth(),
        SpotifyCatalog(SequencedSearchClient()),
        player,
    )
    runtime.local_ai_service = LocalAIService(
        mode="fallback",
        fallback_approved=True,
        adapter=FakeAdapter(),
    )
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post(
        "/command",
        headers={"X-API-Key": "test-key"},
        json={"text": "播放死亡是生命的終點"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["action"] == "spotify_play_track"
    assert ai_calls == ["播放死亡是生命的終點"]
    assert player.tracks == ["resolved"]


def test_command_ambiguous_spotify_result_keeps_ai_out_of_clarification(fake_runtime):
    runtime, *_ = fake_runtime

    def payload(track_id, artist):
        return {
            "id": track_id,
            "uri": f"spotify:track:{track_id}",
            "name": "Stay",
            "artists": [{"name": artist}],
            "album": {"name": "Album"},
        }

    class AmbiguousSearchClient:
        def search_tracks(self, _access_token, _query, *, limit=10):
            return [payload("one", "The Kid LAROI"), payload("two", "The Kid LAROI")]

    class FakeAuth:
        def get_access_token(self):
            return "access-token"

    class NoPlayback:
        def resume(self, *_args, **_kwargs):
            raise AssertionError("ambiguous search must not play")

    class NoAI:
        model_id = "test-model"

        def infer(self, _original_text):
            raise AssertionError("clarification must not invoke Local AI")

    runtime.command_service.spotify = SpotifyService(
        FakeAuth(),
        SpotifyCatalog(AmbiguousSearchClient()),
        NoPlayback(),
    )
    runtime.local_ai_service = LocalAIService(mode="shadow", adapter=NoAI())
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post(
        "/command",
        headers={"X-API-Key": "test-key"},
        json={"text": "播放The Kid LAROI的Stay"},
    )

    assert response.status_code == 200
    assert response.json()["error_code"] == "SPOTIFY_CLARIFICATION_REQUIRED"
    assert response.json()["data"]["clarification_required"] is True


def test_command_clarification_bypasses_local_ai(fake_runtime):
    runtime, *_ = fake_runtime
    calls = []

    class FakeAdapter:
        model_id = "test-model"

        def infer(self, original_text):
            calls.append(original_text)
            raise AssertionError("clarification must not invoke Local AI")

    runtime.local_ai_service = LocalAIService(mode="shadow", adapter=FakeAdapter())

    class FakeClarificationSpotify:
        def execute_clarification(self, text, clarification_token):
            from app.adapters.windows.base import OperationResult

            return OperationResult(True, "已播放。", data={"track_name": "晴天"})

    runtime.command_service.spotify = FakeClarificationSpotify()
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    response = client.post(
        "/command",
        headers={"X-API-Key": "test-key"},
        json={"text": "第一首", "clarification_token": "server-owned-token"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert calls == []
