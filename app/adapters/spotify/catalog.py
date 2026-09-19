"""Spotify search normalization and conservative named-track selection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.chinese import normalize_chinese_text


class SpotifyTrackRef(BaseModel):
    """A server-created reference that is safe to pass to the player adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_id: str = Field(min_length=1, max_length=100)
    track_uri: str = Field(pattern=r"^spotify:track:[A-Za-z0-9]+$", max_length=200)
    track_name: str = Field(min_length=1, max_length=300)
    artist_names: tuple[str, ...] = Field(min_length=1, max_length=10)
    album_name: str = Field(default="", max_length=300)
    album_type: str = Field(default="", max_length=30)
    isrc: str = Field(default="", max_length=30)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    popularity: int | None = Field(default=None, ge=0, le=100)


@dataclass(frozen=True)
class TrackResolution:
    track: SpotifyTrackRef | None
    ambiguous: bool
    candidates: tuple[SpotifyTrackRef, ...] = ()
    retry_signal: str | None = None


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
        if hint == "live":
            return TrackResolution(track=None, ambiguous=False)
        retry_signal: str | None = None
        payloads = self.client.search_tracks(access_token, query, limit=10)
        refs = tuple(
            ref
            for item in payloads
            if (ref := self._to_ref(item)) is not None and self._classify_version(ref) != "live"
        )

        # Chinese song titles can legitimately contain 「的」. The rule parser also
        # uses 「X的Y」 for artist + track, so a bare title such as
        # 「死亡是生命的終點」 may initially be split as artist=死亡是生命,
        # track=終點. Only when that stricter artist+track search returns no usable
        # result, retry the reconstructed phrase as a bare track title.
        if not refs and artist and not album:
            reconstructed_track = f"{artist}的{track}".strip()
            fallback_payloads = self.client.search_tracks(
                access_token,
                f"track:{reconstructed_track}",
                limit=10,
            )
            fallback_refs = tuple(
                ref
                for item in fallback_payloads
                if (ref := self._to_ref(item)) is not None and self._classify_version(ref) != "live"
            )
            if fallback_refs:
                refs = fallback_refs
                track = reconstructed_track
                artist = None
            else:
                retry_signal = "SPOTIFY_ENTITY_SEGMENTATION_RISK"

        if not refs:
            return TrackResolution(track=None, ambiguous=False, retry_signal=retry_signal)

        ranked = sorted(
            refs,
            key=lambda ref: self._ranking_key(ref, track, artist, album, hint),
            reverse=True,
        )
        best_score = self._score(ranked[0], track, artist, album, hint)
        second_score = self._score(ranked[1], track, artist, album, hint) if len(ranked) > 1 else None
        exact_track_matches = [ref for ref in ranked if self._normalize(ref.track_name) == self._normalize(track)]
        if artist is None and album is None and len(exact_track_matches) == 1:
            # A bare request with one exact title match should not lose to
            # near-title results returned by Spotify. Multiple exact matches
            # still go through the normal ambiguity path.
            return TrackResolution(track=exact_track_matches[0], ambiguous=False, candidates=tuple(ranked[:3]))
        title_matches = [ref for ref in ranked if self._similarity(ref.track_name, track) >= 0.80]
        if artist is None and len(title_matches) > 1:
            artist_groups = {
                self._normalize(ref.artist_names[0])
                for ref in title_matches
                if ref.artist_names and self._normalize(ref.artist_names[0])
            }
            if len(artist_groups) > 1:
                return TrackResolution(
                    track=None,
                    ambiguous=True,
                    candidates=self._personalized_candidates(
                        title_matches,
                        track,
                        artist,
                        album,
                        hint,
                        access_token,
                    ),
                )
        if album:
            exact_album_matches = [
                ref for ref in exact_track_matches if self._normalize(ref.album_name) == self._normalize(album)
            ]
            if len(exact_album_matches) == 1:
                return TrackResolution(track=exact_album_matches[0], ambiguous=False, candidates=tuple(ranked[:3]))
            if len(exact_album_matches) > 1:
                album_ranked = sorted(
                    exact_album_matches,
                    key=lambda ref: self._ranking_key(ref, track, artist, album, hint),
                    reverse=True,
                )
                if self._same_recording_group(album_ranked):
                    return TrackResolution(track=album_ranked[0], ambiguous=False, candidates=tuple(album_ranked[:3]))
                return TrackResolution(
                    track=None,
                    ambiguous=True,
                    candidates=self._personalized_candidates(
                        album_ranked,
                        track,
                        artist,
                        album,
                        hint,
                        access_token,
                    ),
                )
        if best_score < 0.70 or (second_score is not None and best_score - second_score < 0.08):
            close_candidates = [
                ref
                for ref in ranked[1:]
                if best_score - self._score(ref, track, artist, album, hint) < 0.08
            ]
            if best_score >= 0.70 and close_candidates and self._same_recording_group(close_candidates + [ranked[0]]):
                return TrackResolution(track=ranked[0], ambiguous=False, candidates=tuple(ranked[:3]))
            if len(ranked) == 1 and best_score < 0.70:
                return TrackResolution(
                    track=None,
                    ambiguous=False,
                    retry_signal="SPOTIFY_LOW_CONFIDENCE_TRACK",
                )
            return TrackResolution(
                track=None,
                ambiguous=True,
                candidates=self._personalized_candidates(
                    ranked,
                    track,
                    artist,
                    album,
                    hint,
                    access_token,
                ),
            )
        return TrackResolution(track=ranked[0], ambiguous=False, candidates=tuple(ranked[:3]))

    def _personalized_candidates(
        self,
        refs: list[SpotifyTrackRef] | tuple[SpotifyTrackRef, ...],
        track: str,
        artist: str | None,
        album: str | None,
        version_hint: str | None,
        access_token: str,
    ) -> tuple[SpotifyTrackRef, ...]:
        """Order the existing top-three ambiguity set with read-only saved status."""

        candidates = tuple(refs[:3])
        checker = getattr(self.client, "check_saved_tracks", None)
        if not callable(checker) or not candidates:
            return candidates
        try:
            statuses = checker(access_token, tuple(ref.track_uri for ref in candidates))
        except Exception:
            return candidates
        if len(statuses) != len(candidates) or any(not isinstance(status, bool) for status in statuses):
            return candidates
        saved_by_uri = dict(zip((ref.track_uri for ref in candidates), statuses))
        return tuple(
            sorted(
                candidates,
                key=lambda ref: (
                    1 if saved_by_uri.get(ref.track_uri, False) else 0,
                    *self._ranking_key(ref, track, artist, album, version_hint),
                ),
                reverse=True,
            )
        )

    @classmethod
    def _to_ref(cls, item: Any) -> SpotifyTrackRef | None:
        if not isinstance(item, dict):
            return None
        artists = item.get("artists")
        album = item.get("album")
        if not isinstance(artists, list) or not isinstance(album, dict):
            return None
        external_ids = item.get("external_ids")
        if not isinstance(external_ids, dict):
            external_ids = {}
        duration_ms = item.get("duration_ms")
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms < 0:
            duration_ms = None
        popularity = item.get("popularity")
        if isinstance(popularity, bool) or not isinstance(popularity, int) or not 0 <= popularity <= 100:
            popularity = None
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
                isrc=str(external_ids.get("isrc", "")).strip(),
                duration_ms=duration_ms,
                popularity=popularity,
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
    def _ranking_key(
        cls,
        ref: SpotifyTrackRef,
        track: str,
        artist: str | None,
        album: str | None = None,
        version_hint: str | None = None,
    ) -> tuple[float, int]:
        """Order equal relevance candidates without changing ambiguity safety."""

        return (
            cls._score(ref, track, artist, album, version_hint),
            ref.popularity if ref.popularity is not None else -1,
        )

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
    def _same_recording_group(cls, refs: list[SpotifyTrackRef]) -> bool:
        """Resolve duplicate releases only when Spotify supplies the same ISRC."""

        if not refs or any(not ref.isrc for ref in refs):
            return False
        isrcs = {ref.isrc.casefold() for ref in refs}
        if len(isrcs) != 1:
            return False
        title_keys = {cls._normalize(ref.track_name) for ref in refs}
        artist_keys = {cls._normalize(ref.artist_names[0]) for ref in refs if ref.artist_names}
        return len(title_keys) == 1 and len(artist_keys) == 1

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
        return normalize_chinese_text(value)
