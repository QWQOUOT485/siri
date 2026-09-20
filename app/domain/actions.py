"""Closed action vocabulary used by both the HTTP API and the parser."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class SpotifyVersionHint(str, Enum):
    """Closed version intent understood by the Spotify catalog ranker."""

    LIVE = "live"
    STUDIO = "studio"
    ORIGINAL = "original"


class ActionName(str, Enum):
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    FORCE_CLOSE_APP = "force_close_app"
    OPEN_WEBSITE = "open_website"
    SPOTIFY_RESUME = "spotify_resume"
    SPOTIFY_PAUSE = "spotify_pause"
    SPOTIFY_NEXT = "spotify_next"
    SPOTIFY_PREVIOUS = "spotify_previous"
    SPOTIFY_PLAY_TRACK = "spotify_play_track"
    SPOTIFY_SHUFFLE_ON = "spotify_shuffle_on"
    SPOTIFY_SHUFFLE_OFF = "spotify_shuffle_off"
    SPOTIFY_REPEAT_OFF = "spotify_repeat_off"
    SPOTIFY_REPEAT_TRACK = "spotify_repeat_track"
    SPOTIFY_REPEAT_CONTEXT = "spotify_repeat_context"
    SPOTIFY_CONTINUE = "spotify_continue"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    SET_VOLUME = "set_volume"
    MUTE = "mute"
    UNMUTE = "unmute"
    TOGGLE_MUTE = "toggle_mute"
    LOCK = "lock"
    REQUEST_SHUTDOWN = "request_shutdown"
    CONFIRM_SHUTDOWN = "confirm_shutdown"
    REFRESH_APPS = "refresh_apps"


APP_ACTIONS = {
    ActionName.OPEN_APP,
    ActionName.CLOSE_APP,
    ActionName.FORCE_CLOSE_APP,
}
WEBSITE_ACTIONS = {ActionName.OPEN_WEBSITE}
VOLUME_ACTIONS = {
    ActionName.VOLUME_UP,
    ActionName.VOLUME_DOWN,
    ActionName.SET_VOLUME,
    ActionName.MUTE,
    ActionName.UNMUTE,
    ActionName.TOGGLE_MUTE,
}
SPOTIFY_TRACK_ACTIONS = {ActionName.SPOTIFY_PLAY_TRACK}
SPOTIFY_STATE_ACTIONS = {
    ActionName.SPOTIFY_SHUFFLE_ON,
    ActionName.SPOTIFY_SHUFFLE_OFF,
    ActionName.SPOTIFY_REPEAT_OFF,
    ActionName.SPOTIFY_REPEAT_TRACK,
    ActionName.SPOTIFY_REPEAT_CONTEXT,
    ActionName.SPOTIFY_CONTINUE,
}
SPOTIFY_ACTIONS = {
    ActionName.SPOTIFY_RESUME,
    ActionName.SPOTIFY_PAUSE,
    ActionName.SPOTIFY_NEXT,
    ActionName.SPOTIFY_PREVIOUS,
    ActionName.SPOTIFY_PLAY_TRACK,
    *SPOTIFY_STATE_ACTIONS,
}


class ValidatedAction(BaseModel):
    """An action after it has crossed the parser/API validation boundary.

    There is deliberately no path, executable, shell command, URL, or arbitrary
    argument field here.  Targets are names/IDs resolved against local catalogs.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: ActionName
    app_id: str | None = Field(default=None, min_length=1, max_length=160)
    app_query: str | None = Field(default=None, min_length=1, max_length=200)
    website_id: str | None = Field(default=None, min_length=1, max_length=100)
    website_query: str | None = Field(default=None, min_length=1, max_length=200)
    track: str | None = Field(default=None, min_length=1, max_length=300)
    artist: str | None = Field(default=None, min_length=1, max_length=300)
    album: str | None = Field(default=None, min_length=1, max_length=300)
    version_hint: SpotifyVersionHint | None = None
    volume_percent: StrictInt | None = Field(default=None, ge=0, le=100)
    steps: int = Field(default=1, ge=1, le=10)
    confirmation_token: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "ValidatedAction":
        if self.action in APP_ACTIONS and not (self.app_id or self.app_query):
            raise ValueError("app_id or app_query is required for an application action")
        if self.action in WEBSITE_ACTIONS and not (self.website_id or self.website_query):
            raise ValueError("website_id or website_query is required for open_website")
        if self.action is ActionName.CONFIRM_SHUTDOWN and not self.confirmation_token:
            raise ValueError("confirmation_token is required")
        if self.action in SPOTIFY_TRACK_ACTIONS and not self.track:
            raise ValueError("track is required for Spotify named-track playback")
        if self.action not in SPOTIFY_TRACK_ACTIONS and (self.track or self.artist or self.album or self.version_hint):
            raise ValueError("track, artist, album, and version_hint are only supported by Spotify named-track playback")
        if self.action is ActionName.SET_VOLUME and self.volume_percent is None:
            raise ValueError("volume_percent is required for set_volume")
        if self.action is not ActionName.SET_VOLUME and self.volume_percent is not None:
            raise ValueError("volume_percent is only supported by set_volume")
        for value in (self.track, self.artist, self.album):
            if value and any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError("track, artist, and album must not contain control characters")
        if self.action is ActionName.SET_VOLUME and self.steps != 1:
            raise ValueError("steps is not supported by set_volume")
        if self.action not in VOLUME_ACTIONS and self.steps != 1:
            raise ValueError("steps is only supported by volume actions")
        return self


class ParsedCommand(BaseModel):
    """Result of the intentionally small rule-based natural-language parser."""

    model_config = ConfigDict(extra="forbid")

    action: ValidatedAction | None = None
    accepted: bool = False
    error_code: str | None = None
    message: str


def action_payload(action: ValidatedAction) -> dict[str, Any]:
    """Return a safe, loggable representation without secrets."""

    payload = action.model_dump(exclude_none=True)
    if "confirmation_token" in payload:
        payload["confirmation_token"] = "[redacted]"
    return payload
