"""Platform-neutral Spotify adapter models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SpotifyDevice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    device_id: str = Field(alias="id", min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    is_active: bool = False
    is_restricted: bool = False

    @classmethod
    def from_payload(cls, payload: dict) -> "SpotifyDevice":
        return cls(
            id=str(payload.get("id", "")).strip(),
            name=str(payload.get("name", "")).strip(),
            is_active=bool(payload.get("is_active", False)),
            is_restricted=bool(payload.get("is_restricted", False)),
        )
