"""Deterministic gate deciding whether a Spotify semantic retry is allowed."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.actions import ActionName, ParsedCommand
from app.domain.local_ai import MAX_AI_SLOT_LENGTH
from app.domain.matching import normalize_name
from .semantic_grounder import contains_forbidden_authority


_RETRYABLE_RESOLUTION_ERRORS = frozenset(
    {
        "SPOTIFY_TRACK_NOT_FOUND",
        "SPOTIFY_LOW_CONFIDENCE_TRACK",
        "SPOTIFY_ENTITY_SEGMENTATION_RISK",
    }
)
_PLAY_PREFIXES = (
    "播放音樂", "播放音乐", "播放", "想聽", "想听", "我要聽", "我要听", "幫我放", "帮我放",
    "請播放", "请播放", "聽", "听", "播", "spotify play", "play ", "listen to ", "put on ",
)


@dataclass(frozen=True)
class AIEligibility:
    eligible: bool
    reason: str


class SemanticRetryEligibilityGate:
    """Reject unsafe or irrelevant text before it reaches the model."""

    def evaluate(
        self,
        text: str,
        parsed: ParsedCommand,
        *,
        deterministic_success: bool = False,
        deterministic_error_code: str | None = None,
        clarification_token_present: bool = False,
    ) -> AIEligibility:
        raw = (text or "").strip()
        if clarification_token_present:
            return AIEligibility(False, "clarification_token_bypasses_ai")
        if not raw or len(raw) > MAX_AI_SLOT_LENGTH:
            return AIEligibility(False, "input_out_of_bounds")
        if any(ord(char) < 32 or ord(char) == 127 for char in raw):
            return AIEligibility(False, "control_character")
        if contains_forbidden_authority(raw):
            return AIEligibility(False, "hostile_input")
        if not self._looks_like_spotify_play_request(raw):
            return AIEligibility(False, "unsupported_domain")

        if parsed.accepted and parsed.action is not None:
            if parsed.action.action is not ActionName.SPOTIFY_PLAY_TRACK:
                return AIEligibility(False, "deterministic_non_track_action")
            if deterministic_success:
                return AIEligibility(False, "deterministic_success")
            if deterministic_error_code not in _RETRYABLE_RESOLUTION_ERRORS:
                return AIEligibility(False, "resolver_failure_not_retryable")
            return AIEligibility(True, "parser_success_resolver_failure")

        if parsed.error_code not in {None, "INVALID_COMMAND"}:
            return AIEligibility(False, "parser_rejected_non_retryable")
        return AIEligibility(True, "parser_miss")

    @staticmethod
    def _looks_like_spotify_play_request(text: str) -> bool:
        normalized = normalize_name(text).casefold()
        if re.match(r"^(?:spotify\s+)?(?:play|listen\s+to|put\s+on)\b", normalized):
            return True
        return any(text.strip().casefold().startswith(prefix.casefold()) for prefix in _PLAY_PREFIXES)
