"""Spotify search normalization and conservative named-track selection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpotifyTrackRef(BaseModel):
    """A server-created reference that is safe to pass to the player adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_id: str = Field(min_length=1, max_length=100)
    track_uri: str = Field(pattern=r"^spotify:track:[A-Za-z0-9]+$", max_length=200)
    track_name: str = Field(min_length=1, max_length=300)
    artist_names: tuple[str, ...] = Field(min_length=1, max_length=10)
    album_name: str = Field(default="", max_length=300)


@dataclass(frozen=True)
class TrackResolution:
    track: SpotifyTrackRef | None
    ambiguous: bool
    candidates: tuple[SpotifyTrackRef, ...] = ()


class SpotifyCatalog:
    """Expose one deep search interface over the external Spotify catalog."""

    def __init__(self, client) -> None:
        self.client = client

    def find_track(self, track: str, artist: str | None, *, access_token: str) -> TrackResolution:
        query = f"track:{track}"
        if artist:
            query += f" artist:{artist}"
        payloads = self.client.search_tracks(access_token, query, limit=10)
        refs = tuple(ref for item in payloads if (ref := self._to_ref(item)) is not None)
        if not refs:
            return TrackResolution(track=None, ambiguous=False)

        ranked = sorted(refs, key=lambda ref: self._score(ref, track, artist), reverse=True)
        best_score = self._score(ranked[0], track, artist)
        second_score = self._score(ranked[1], track, artist) if len(ranked) > 1 else None
        exact_track_matches = [ref for ref in ranked if self._normalize(ref.track_name) == self._normalize(track)]
        if artist is None and len(exact_track_matches) > 1:
            return TrackResolution(track=None, ambiguous=True, candidates=tuple(exact_track_matches[:5]))
        if best_score < 0.70 or (second_score is not None and best_score - second_score < 0.08):
            return TrackResolution(track=None, ambiguous=True, candidates=tuple(ranked[:5]))
        return TrackResolution(track=ranked[0], ambiguous=False, candidates=tuple(ranked[:5]))

    @classmethod
    def _to_ref(cls, item: Any) -> SpotifyTrackRef | None:
        if not isinstance(item, dict):
            return None
        artists = item.get("artists")
        album = item.get("album")
        if not isinstance(artists, list) or not isinstance(album, dict):
            return None
        names = tuple(
            str(artist.get("name", "")).strip()
            for artist in artists
            if isinstance(artist, dict) and str(artist.get("name", "")).strip()
        )
        try:
            return SpotifyTrackRef(
                track_id=str(item.get("id", "")).strip(),
                track_uri=str(item.get("uri", "")).strip(),
                track_name=str(item.get("name", "")).strip(),
                artist_names=names,
                album_name=str(album.get("name", "")).strip(),
            )
        except Exception:
            return None

    @classmethod
    def _score(cls, ref: SpotifyTrackRef, track: str, artist: str | None) -> float:
        track_score = cls._similarity(ref.track_name, track)
        if not artist:
            return track_score
        artist_score = max((cls._similarity(name, artist) for name in ref.artist_names), default=0.0)
        return track_score * 0.75 + artist_score * 0.25

    @classmethod
    def _similarity(cls, left: str, right: str) -> float:
        left_normalized = cls._normalize(left)
        right_normalized = cls._normalize(right)
        if left_normalized == right_normalized:
            return 1.0
        if not left_normalized or not right_normalized:
            return 0.0
        return SequenceMatcher(None, left_normalized, right_normalized).ratio()

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", normalized, flags=re.UNICODE)
        return " ".join(normalized.split())
