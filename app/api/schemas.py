"""Strict request models with no path/URL/command fields."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.actions import ActionName, SpotifyVersionHint, ValidatedAction


_UNSAFE_TARGET = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/|\.exe\b|\.bat\b|\.cmd\b|https?://|[;&|`$<>]|\x00)", re.IGNORECASE)


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: ActionName
    app_id: str | None = Field(default=None, min_length=1, max_length=160)
    app_name: str | None = Field(default=None, min_length=1, max_length=200)
    website_id: str | None = Field(default=None, min_length=1, max_length=100)
    website_name: str | None = Field(default=None, min_length=1, max_length=200)
    track: str | None = Field(default=None, min_length=1, max_length=200)
    artist: str | None = Field(default=None, min_length=1, max_length=200)
    album: str | None = Field(default=None, min_length=1, max_length=200)
    version_hint: SpotifyVersionHint | None = None
    steps: int = Field(default=1, ge=1, le=10)
    confirmation_token: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def reject_unsafe_remote_values(self) -> "ActionRequest":
        for value in (self.app_name, self.website_name):
            if value and _UNSAFE_TARGET.search(value):
                raise ValueError("remote target must be a catalog name, not a path, URL, or command")
        if self.action in {ActionName.OPEN_APP, ActionName.CLOSE_APP, ActionName.FORCE_CLOSE_APP} and not (self.app_id or self.app_name):
            raise ValueError("app_id or app_name is required")
        if self.action is ActionName.OPEN_WEBSITE and not (self.website_id or self.website_name):
            raise ValueError("website_id or website_name is required")
        if self.action is ActionName.CONFIRM_SHUTDOWN and not self.confirmation_token:
            raise ValueError("confirmation_token is required")
        for value in (self.track, self.artist, self.album):
            if value and any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError("track, artist, and album must not contain control characters")
        if self.action is ActionName.SPOTIFY_PLAY_TRACK and not self.track:
            raise ValueError("track is required for Spotify named-track playback")
        if self.action is not ActionName.SPOTIFY_PLAY_TRACK and (self.track or self.artist or self.album or self.version_hint):
            raise ValueError("track, artist, album, and version_hint are only supported by Spotify named-track playback")
        if self.action not in {ActionName.VOLUME_UP, ActionName.VOLUME_DOWN, ActionName.MUTE, ActionName.UNMUTE, ActionName.TOGGLE_MUTE} and self.steps != 1:
            raise ValueError("steps is only supported by volume actions")
        return self

    def to_validated(self) -> ValidatedAction:
        return ValidatedAction(
            action=self.action,
            app_id=self.app_id,
            app_query=self.app_name,
            website_id=self.website_id,
            website_query=self.website_name,
            track=self.track,
            artist=self.artist,
            album=self.album,
            version_hint=self.version_hint,
            steps=self.steps,
            confirmation_token=self.confirmation_token,
        )


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=300)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=200)


def response_payload(result) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": result.success,
        "status": result.status,
        "action": result.action,
        "message": result.message,
        "candidates": result.candidates,
        "confirmation_required": result.confirmation_required,
        "error_code": result.error_code,
        "data": result.data,
    }
    if result.confirmation_token:
        payload["confirmation_token"] = result.confirmation_token
    return payload
