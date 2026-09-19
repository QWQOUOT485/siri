"""In-process, sanitized fail-closed evidence for the Local AI promotion gate.

These tests deliberately use fake adapters and never read production config,
call LM Studio, or create a trusted execution target.  They are source/unit
evidence only; the real-Agent transport fault matrix remains a separate gate.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from app.adapters.local_ai import (
    LMStudioLocalAIAdapter,
    LocalAIResponse,
    LocalAITransportError,
)
from app.domain.actions import ParsedCommand
from app.domain.local_ai import RawAIIntent
from app.services.ai_policy import AIPolicyResult
from app.services.local_ai_service import LocalAIService
from app.services.semantic_grounder import SemanticGrounder


def parser_miss(text: str = "播放晴天") -> ParsedCommand:
    return ParsedCommand(accepted=False, error_code="INVALID_COMMAND", message=text)


def _payload(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "intent": "spotify_play_track",
        "track": "晴天",
        "artist": None,
        "album": None,
    }
    payload.update(overrides)
    return payload


class StaticAdapter:
    model_id = "matrix-model"

    def __init__(self, content: str):
        self.content = content

    def infer(self, _original_text: str) -> LocalAIResponse:
        return LocalAIResponse(content=self.content, model_id=self.model_id, latency_ms=1.0)


class FailingAdapter:
    model_id = "matrix-model"

    def __init__(self, reason: str):
        self.reason = reason

    def infer(self, _original_text: str) -> LocalAIResponse:
        raise LocalAITransportError(self.reason)


def _json_adapter(payload: dict[str, object]) -> StaticAdapter:
    return StaticAdapter(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize(
    ("case", "adapter", "expected_status", "expected_reason"),
    (
        (
            "malformed_model_json",
            StaticAdapter("not-json"),
            "schema_rejected",
            "strict_schema_rejected",
        ),
        (
            "malformed_schema_authority_field",
            _json_adapter({**_payload(), "track_id": "spotify-track-id"}),
            "schema_rejected",
            "strict_schema_rejected",
        ),
        (
            "connection_or_timeout",
            FailingAdapter("connection_or_timeout"),
            "transport_error",
            "connection_or_timeout",
        ),
        (
            "single_flight_busy",
            FailingAdapter("busy"),
            "transport_error",
            "busy",
        ),
        (
            "oversized_response",
            FailingAdapter("response_too_large"),
            "transport_error",
            "response_too_large",
        ),
        (
            "ungrounded_track",
            _json_adapter({**_payload(), "track": "不存在"}),
            "grounding_rejected",
            "track_not_grounded",
        ),
    ),
    ids=[
        "malformed_model_json",
        "malformed_schema_authority_field",
        "connection_or_timeout",
        "single_flight_busy",
        "oversized_response",
        "ungrounded_track",
    ],
)
def test_fail_closed_matrix_never_creates_action(case, adapter, expected_status, expected_reason):
    result = LocalAIService(mode="shadow", adapter=adapter).retry("播放晴天", parser_miss("播放晴天"))

    assert result.status == expected_status, case
    assert result.reason == expected_reason, case
    assert result.action is None, case
    assert result.execution_allowed is False, case


def test_connection_refused_is_category_only_transport_failure():
    class RefusedOpener:
        def open(self, _request, timeout):
            assert timeout == 2.0
            raise urllib.error.URLError(ConnectionRefusedError("local service unavailable"))

    adapter = LMStudioLocalAIAdapter(
        "http://127.0.0.1:1234/v1",
        "matrix-model",
        opener=RefusedOpener(),
    )

    with pytest.raises(LocalAITransportError) as exc_info:
        adapter.infer("播放晴天")

    assert exc_info.value.reason == "connection_or_timeout"


def test_invented_optional_slots_are_removed_before_policy():
    raw = RawAIIntent.model_validate(
        _payload(artist="周杰倫", album="葉惠美"),
        strict=True,
    )

    result = SemanticGrounder().ground("播放晴天", raw)

    assert result.accepted is True
    assert result.grounded is not None
    assert result.grounded.track == "晴天"
    assert result.grounded.artist is None
    assert result.grounded.album is None


def test_policy_rejection_is_fail_closed_even_after_grounding():
    class RejectingPolicy:
        def apply(self, _grounded):
            return AIPolicyResult(False, "policy_rejected")

    result = LocalAIService(
        mode="shadow",
        adapter=_json_adapter(_payload()),
        policy_gate=RejectingPolicy(),
    ).retry("播放晴天", parser_miss("播放晴天"))

    assert result.status == "policy_rejected"
    assert result.reason == "policy_rejected"
    assert result.action is None
    assert result.execution_allowed is False
