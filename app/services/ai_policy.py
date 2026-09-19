"""Deterministic policy gate between grounded AI intent and trusted action."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.actions import ActionName, ValidatedAction
from app.domain.local_ai import GroundedAIIntent


@dataclass(frozen=True)
class AIPolicyResult:
    accepted: bool
    reason: str
    action: ValidatedAction | None = None


class AIPolicyGate:
    """Keep the Local AI allowlist smaller than the global action vocabulary."""

    def apply(self, grounded: GroundedAIIntent | None) -> AIPolicyResult:
        if grounded is None:
            return AIPolicyResult(False, "grounding_missing")
        if grounded.intent == "unknown":
            return AIPolicyResult(True, "accepted_unknown")
        if grounded.intent != "spotify_play_track" or not grounded.track:
            return AIPolicyResult(False, "intent_not_allowlisted")

        try:
            action = ValidatedAction(
                action=ActionName.SPOTIFY_PLAY_TRACK,
                track=grounded.track,
                artist=grounded.artist,
                album=grounded.album,
            )
        except ValueError:
            return AIPolicyResult(False, "validated_action_rejected")
        return AIPolicyResult(True, "accepted_spotify_play_track", action)
