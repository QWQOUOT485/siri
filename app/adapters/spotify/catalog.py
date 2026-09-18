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
    album_type: str = Field(default="", max_length=30)


@dataclass(frozen=True)
class TrackResolution:
    track: SpotifyTrackRef | None
    ambiguous: bool
    candidates: tuple[SpotifyTrackRef, ...] = ()


class SpotifyCatalog:
    """Expose one deep search interface over the external Spotify catalog."""

    def __init__(self, client) -> None:
        self.client = client

    def find_track(
        self,
        track: str,
        artist: str | None,
        album: str | None = None,
        *,
        version_hint: str | None = None,
        access_token: str,
    ) -> TrackResolution:
        query = f"track:{track}"
        if artist:
            query += f" artist:{artist}"
        if album:
            query += f" album:{album}"
        hint = self._hint_value(version_hint)
        if hint:
            query += f" {hint}"
        payloads = self.client.search_tracks(access_token, query, limit=10)
        refs = tuple(ref for item in payloads if (ref := self._to_ref(item)) is not None)
        if not refs:
            return TrackResolution(track=None, ambiguous=False)

        ranked = sorted(refs, key=lambda ref: self._score(ref, track, artist, album, hint), reverse=True)
        best_score = self._score(ranked[0], track, artist, album, hint)
        second_score = self._score(ranked[1], track, artist, album, hint) if len(ranked) > 1 else None
        exact_track_matches = [ref for ref in ranked if self._normalize(ref.track_name) == self._normalize(track)]
        title_matches = [ref for ref in ranked if self._similarity(ref.track_name, track) >= 0.80]
        if artist is None and len(title_matches) > 1:
            artist_groups = {
                self._normalize(ref.artist_names[0])
                for ref in title_matches
                if ref.artist_names and self._normalize(ref.artist_names[0])
            }
            if len(artist_groups) > 1:
                return TrackResolution(track=None, ambiguous=True, candidates=tuple(title_matches[:5]))
        if album:
            exact_album_matches = [
                ref for ref in exact_track_matches if self._normalize(ref.album_name) == self._normalize(album)
            ]
            if len(exact_album_matches) == 1:
                return TrackResolution(track=exact_album_matches[0], ambiguous=False, candidates=tuple(ranked[:5]))
            if len(exact_album_matches) > 1:
                return TrackResolution(track=None, ambiguous=True, candidates=tuple(exact_album_matches[:5]))
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
                album_type=str(album.get("album_type", "")).strip(),
            )
        except Exception:
            return None

    @classmethod
    def _score(
        cls,
        ref: SpotifyTrackRef,
        track: str,
        artist: str | None,
        album: str | None = None,
        version_hint: str | None = None,
    ) -> float:
        track_score = cls._similarity(ref.track_name, track)
        if not artist and not album:
            base_score = track_score
        else:
            artist_score = max((cls._similarity(name, artist) for name in ref.artist_names), default=0.0) if artist else None
            album_score = cls._similarity(ref.album_name, album) if album else None
            if artist and album:
                base_score = track_score * 0.60 + (artist_score or 0.0) * 0.20 + (album_score or 0.0) * 0.20
            elif artist:
                base_score = track_score * 0.75 + (artist_score or 0.0) * 0.25
            else:
                base_score = track_score * 0.75 + (album_score or 0.0) * 0.25
        return base_score + cls._version_bonus(ref, version_hint)

    @classmethod
    def _version_bonus(cls, ref: SpotifyTrackRef, version_hint: str | None) -> float:
        hint = cls._hint_value(version_hint)
        classification = cls._classify_version(ref)
        if hint == "live":
            if classification == "live":
                return 0.18
            if classification == "studio":
                return -0.10
            return 0.0
        if hint in {"studio", "original"}:
            if classification == "studio":
                return 0.16
            if classification == "live":
                return -0.18
            return 0.0
        if classification == "live":
            return -0.18
        if classification == "secondary":
            return -0.08
        return 0.08

    @classmethod
    def _classify_version(cls, ref: SpotifyTrackRef) -> str:
        searchable = f"{ref.track_name} {ref.album_name}"
        if cls._contains_marker(searchable, cls._LIVE_MARKERS):
            return "live"
        if ref.album_type.casefold() == "compilation" or cls._contains_marker(searchable, cls._SECONDARY_MARKERS):
            return "secondary"
        return "studio"

    _LIVE_MARKERS = ("live", "concert", "tour", "演唱會", "演唱会", "現場", "现场")
    _SECONDARY_MARKERS = (
        "acoustic",
        "remix",
        "karaoke",
        "tribute",
        "cover",
        "demo",
        "deluxe",
        "remaster",
        "anniversary",
        "reissue",
        "re-release",
        "compilation",
        "翻唱",
        "伴奏",
        "精選",
        "精选",
    )

    @classmethod
    def _contains_marker(cls, value: str, markers: tuple[str, ...]) -> bool:
        normalized = cls._normalize(value)
        for marker in markers:
            if re.fullmatch(r"[a-z0-9-]+", marker):
                if re.search(rf"\b{re.escape(marker)}\b", normalized):
                    return True
            elif marker in normalized:
                return True
        return False

    @staticmethod
    def _hint_value(version_hint: str | None) -> str | None:
        if version_hint is None:
            return None
        value = getattr(version_hint, "value", version_hint)
        return str(value).casefold()

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
