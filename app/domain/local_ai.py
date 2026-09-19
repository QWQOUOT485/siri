"""Closed, untrusted Local AI intent models.

These models intentionally stop before Spotify resolution or execution.  A
schema-valid :class:`RawAIIntent` is still untrusted until the deterministic
grounder and policy gate accept it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator


AIIntentName = Literal["spotify_play_track", "unknown"]
AI_SCHEMA_VERSION = 1
MAX_AI_SLOT_LENGTH = 300


class _IntentSlots(BaseModel):
    """Shared closed slot shape for raw and grounded trust states."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intent: AIIntentName
    track: StrictStr | None = Field(default=None, min_length=1, max_length=MAX_AI_SLOT_LENGTH)
    artist: StrictStr | None = Field(default=None, min_length=1, max_length=MAX_AI_SLOT_LENGTH)
    album: StrictStr | None = Field(default=None, min_length=1, max_length=MAX_AI_SLOT_LENGTH)

    @model_validator(mode="after")
    def validate_intent_slots(self):
        if self.intent == "spotify_play_track" and self.track is None:
            raise ValueError("spotify_play_track requires a track")
        if self.intent == "unknown" and any((self.track, self.artist, self.album)):
            raise ValueError("unknown cannot carry semantic slots")
        for value in (self.track, self.artist, self.album):
            if value and any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError("AI slots must not contain control characters")
        return self


class RawAIIntent(_IntentSlots):
    """Strict model output, before deterministic grounding."""

    schema_version: Literal[1]


class GroundedAIIntent(_IntentSlots):
    """Intent whose slots were supported by spans in the original utterance."""

    pass
