"""Spotify search normalization and conservative named-track selection."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.spotify.personalization_cache import SpotifyPersonalizationCache
from app.domain.chinese import normalize_chinese_text


class SpotifyTrackRef(BaseModel):
    """A server-created reference that is safe to pass to the player adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_id: str = Field(min_length=1, max_length=100)
    track_uri: str = Field(pattern=r"^spotify:track:[A-Za-z0-9]+$", max_length=200)
    track_name: str = Field(min_length=1, max_length=300)
    artist_names: tuple[str, ...] = Field(min_length=1, max_length=10)
    # Trusted provider identity metadata used only for post-clarification
    # alias learning.  It is never accepted from the client or passed as a
    # playback target.
    artist_ids: tuple[str | None, ...] = Field(default=(), max_length=10)
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
    # The first public page is still bounded to three candidates.  This
    # server-owned pool lets the clarification store offer a later page
    # without exposing provider IDs or accepting a client-controlled offset.
    recovery_candidates: tuple[SpotifyTrackRef, ...] = ()


_PersonalizationValue = TypeVar("_PersonalizationValue")


class SpotifyCatalog:
    """Expose one deep search interface over the external Spotify catalog."""

    _MIN_SAFE_TRACK_SCORE = 0.70
    _INITIAL_SEARCH_LIMIT = 10
    _RECOVERY_SEARCH_LIMIT = 10
    _MAX_RECOVERY_POOL = 20

    def __init__(self, client, *, personalization_cache: SpotifyPersonalizationCache | None = None) -> None:
        self.client = client
        self.personalization_cache = personalization_cache or SpotifyPersonalizationCache()

    def find_track(
        self,
        track: str,
        artist: str | None,
        album: str | None = None,
        *,
        version_hint: str | None = None,
        source_text: str | None = None,
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
        payloads = self.client.search_tracks(access_token, query, limit=self._INITIAL_SEARCH_LIMIT)
        refs = self._refs_from_payloads(payloads)

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
                limit=self._INITIAL_SEARCH_LIMIT,
            )
            fallback_refs = self._refs_from_payloads(fallback_payloads)
            if fallback_refs:
                refs = fallback_refs
                track = reconstructed_track
                artist = None
            elif self._has_explicit_chinese_artist_track_shape(source_text, artist, track):
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
                candidates = self._personalized_candidates(
                    title_matches,
                    track,
                    artist,
                    album,
                    hint,
                    access_token,
                )
                return TrackResolution(
                    track=None,
                    ambiguous=True,
                    candidates=candidates,
                    recovery_candidates=self._recovery_pool(ranked, candidates),
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
                candidates = self._personalized_candidates(
                    album_ranked,
                    track,
                    artist,
                    album,
                    hint,
                    access_token,
                )
                return TrackResolution(
                    track=None,
                    ambiguous=True,
                    candidates=candidates,
                    recovery_candidates=self._recovery_pool(album_ranked, candidates),
                )
        if best_score < self._MIN_SAFE_TRACK_SCORE or (
            second_score is not None and best_score - second_score < 0.08
        ):
            close_candidates = [
                ref
                for ref in ranked[1:]
                if best_score - self._score(ref, track, artist, album, hint) < 0.08
            ]
            if (
                best_score >= self._MIN_SAFE_TRACK_SCORE
                and close_candidates
                and self._same_recording_group(close_candidates + [ranked[0]])
            ):
                return TrackResolution(track=ranked[0], ambiguous=False, candidates=tuple(ranked[:3]))
            if len(ranked) == 1 and best_score < self._MIN_SAFE_TRACK_SCORE:
                return TrackResolution(
                    track=None,
                    ambiguous=False,
                    retry_signal="SPOTIFY_LOW_CONFIDENCE_TRACK",
                )
            candidates = self._personalized_candidates(
                ranked,
                track,
                artist,
                album,
                hint,
                access_token,
            )
            return TrackResolution(
                track=None,
                ambiguous=True,
                candidates=candidates,
                recovery_candidates=self._recovery_pool(ranked, candidates),
            )
        return TrackResolution(track=ranked[0], ambiguous=False, candidates=tuple(ranked[:3]))

    def recover_candidates(
        self,
        track: str,
        artist: str | None,
        album: str | None = None,
        *,
        version_hint: str | None = None,
        source_text: str | None = None,
        access_token: str,
        exclude_track_ids: tuple[str, ...] = (),
        offset: int = 0,
    ) -> tuple[SpotifyTrackRef, ...]:
        """Fetch bounded, server-owned evidence for a later clarification page.

        Recovery deliberately never returns an automatically selected track.
        It may relax the failed artist segmentation into title-first Spotify
        evidence, but the result remains a clarification-only candidate set.
        The offset is computed by the server from the live clarification
        context; it is never accepted from the HTTP client.
        """

        if not isinstance(track, str) or not 1 <= len(track.strip()) <= 300:
            return ()
        if self._hint_value(version_hint) == "live":
            return ()
        offset = max(0, min(int(offset), 50))
        excluded = {
            value.strip()
            for value in exclude_track_ids
            if isinstance(value, str) and 1 <= len(value.strip()) <= 100
        }
        refs_by_id: dict[str, SpotifyTrackRef] = {}
        for query in self._recovery_queries(track, artist, album, source_text):
            payloads = self._search_tracks(
                access_token,
                query,
                limit=self._RECOVERY_SEARCH_LIMIT,
                offset=offset,
            )
            for ref in self._refs_from_payloads(payloads):
                if ref.track_id not in refs_by_id:
                    refs_by_id[ref.track_id] = ref
                if len(refs_by_id) >= self._MAX_RECOVERY_POOL:
                    break
            if len(refs_by_id) >= self._MAX_RECOVERY_POOL:
                break

        refs = [ref for ref in refs_by_id.values() if ref.track_id not in excluded]
        if not refs:
            return ()

        # Recovery is still title-grounded evidence.  A weakly related result
        # must not become a new clarification candidate merely because the
        # first constrained search failed.
        title_matches = [
            ref
            for ref in refs
            if self._similarity(ref.track_name, track) >= 0.80
        ]
        if not title_matches:
            return ()
        refs = title_matches

        # An explicit album is a hard search constraint.  Artist text may be
        # ASR-corrupted, so title-first recovery can surface other artists,
        # but never auto-selects them; the existing clarification boundary
        # remains mandatory.
        if album:
            album_matches = [
                ref for ref in refs if self._normalize(ref.album_name) == self._normalize(album)
            ]
            if album_matches:
                refs = album_matches
            else:
                return ()

        hint = self._hint_value(version_hint)
        ranked = sorted(
            refs,
            key=lambda ref: self._ranking_key(ref, track, artist, album, hint),
            reverse=True,
        )
        personalized = self._personalized_candidates(
            ranked,
            track,
            artist,
            album,
            hint,
            access_token,
        )
        return self._recovery_pool(ranked, personalized)

    @classmethod
    def _recovery_queries(
        cls,
        track: str,
        artist: str | None,
        album: str | None,
        source_text: str | None,
    ) -> tuple[str, ...]:
        title_query = f"track:{track}"
        if album:
            title_query += f" album:{album}"
        return (title_query,)

    def _search_tracks(self, access_token: str, query: str, *, limit: int, offset: int) -> list[dict[str, Any]]:
        """Call the fixed search adapter with a server-owned bounded offset."""

        try:
            return self.client.search_tracks(access_token, query, limit=limit, offset=offset)
        except TypeError as exc:
            # Small test doubles and older local adapters may not expose the
            # optional offset yet.  Only offset zero may safely fall back;
            # silently repeating a later page would weaken bounded recovery.
            if offset != 0 or "offset" not in str(exc):
                raise
            return self.client.search_tracks(access_token, query, limit=limit)

    @classmethod
    def _refs_from_payloads(cls, payloads: list[dict[str, Any]]) -> tuple[SpotifyTrackRef, ...]:
        refs: list[SpotifyTrackRef] = []
        seen: set[str] = set()
        for item in payloads:
            ref = cls._to_ref(item)
            if ref is None or cls._classify_version(ref) == "live" or ref.track_id in seen:
                continue
            seen.add(ref.track_id)
            refs.append(ref)
        return tuple(refs)

    @classmethod
    def _recovery_pool(
        cls,
        ranked: list[SpotifyTrackRef] | tuple[SpotifyTrackRef, ...],
        first_page: tuple[SpotifyTrackRef, ...],
    ) -> tuple[SpotifyTrackRef, ...]:
        """Keep the personalized public page first, then deterministic tail."""

        result: list[SpotifyTrackRef] = []
        seen: set[str] = set()
        for ref in (*first_page, *ranked):
            if ref.track_id in seen:
                continue
            seen.add(ref.track_id)
            result.append(ref)
            if len(result) >= cls._MAX_RECOVERY_POOL:
                break
        return tuple(result)

    def _personalized_candidates(
        self,
        refs: list[SpotifyTrackRef] | tuple[SpotifyTrackRef, ...],
        track: str,
        artist: str | None,
        album: str | None,
        version_hint: str | None,
        access_token: str,
    ) -> tuple[SpotifyTrackRef, ...]:
        """Order the existing top-three ambiguity set with read-only user signals."""

        candidates = tuple(refs[:3])
        saved_by_uri: dict[str, bool] = {}
        checker = getattr(self.client, "check_saved_tracks", None)
        if not callable(checker) or not candidates:
            return candidates
        try:
            statuses = checker(access_token, tuple(ref.track_uri for ref in candidates))
        except Exception:
            return candidates
        if len(statuses) != len(candidates) or not all(isinstance(status, bool) for status in statuses):
            return candidates
        saved_by_uri = dict(zip((ref.track_uri for ref in candidates), statuses))
        top_track_ids = self._top_track_ids(access_token)
        top_artist_names = self._top_artist_names(access_token)
        recent_track_ids, recent_artist_names = self._recent_signals(access_token)

        def ranking_key(ref: SpotifyTrackRef) -> tuple[float | int, ...]:
            relevance_score = self._score(ref, track, artist, album, version_hint)
            saved_score = 1 if saved_by_uri.get(ref.track_uri, False) else 0
            top_track_score = 1 if ref.track_id in top_track_ids else 0
            top_artist_score = int(
                any(self._normalize(name) in top_artist_names for name in ref.artist_names)
            )
            recent_track_score = 1 if ref.track_id in recent_track_ids else 0
            recent_artist_score = int(
                any(self._normalize(name) in recent_artist_names for name in ref.artist_names)
            )
            popularity = ref.popularity if ref.popularity is not None else -1
            if artist or album or version_hint:
                # Explicit metadata is a stronger authority than personalization.
                return (
                    relevance_score,
                    saved_score,
                    top_track_score,
                    top_artist_score,
                    recent_track_score,
                    recent_artist_score,
                    popularity,
                )
            return (
                saved_score,
                top_track_score,
                top_artist_score,
                recent_track_score,
                recent_artist_score,
                relevance_score,
                popularity,
            )

        return tuple(
            sorted(
                candidates,
                key=ranking_key,
                reverse=True,
            )
        )

    def _top_track_ids(self, access_token: str) -> set[str]:
        getter = getattr(self.client, "get_top_tracks", None)
        if not callable(getter):
            return set()

        def load() -> frozenset[str] | None:
            items = getter(access_token)
            if not isinstance(items, list):
                return None
            track_ids: set[str] = set()
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
                    return None
                track_ids.add(item["id"].strip())
            return frozenset(track_ids)

        return set(self._cached_personalization(access_token, "top_tracks", load, frozenset()))

    def _top_artist_names(self, access_token: str) -> set[str]:
        getter = getattr(self.client, "get_top_artists", None)
        if not callable(getter):
            return set()

        def load() -> frozenset[str] | None:
            items = getter(access_token)
            if not isinstance(items, list):
                return None
            artist_names: set[str] = set()
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
                    return None
                artist_names.add(self._normalize(item["name"]))
            return frozenset(artist_names)

        return set(self._cached_personalization(access_token, "top_artists", load, frozenset()))

    def _recent_signals(self, access_token: str) -> tuple[set[str], set[str]]:
        """Return only bounded identity evidence from the fixed recent-items read."""

        getter = getattr(self.client, "get_recently_played", None)
        if not callable(getter):
            return set(), set()

        def load() -> tuple[frozenset[str], frozenset[str]] | None:
            items = getter(access_token)
            if not isinstance(items, list):
                return None
            track_ids: set[str] = set()
            artist_names: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    return None
                # The concrete adapter returns Spotify recently-played wrappers;
                # accepting a track-shaped item as well keeps this optional seam
                # compatible with small test/double adapters without widening it.
                track = item.get("track") if "track" in item else item
                if not isinstance(track, dict):
                    return None
                track_id = track.get("id")
                artists = track.get("artists")
                if (
                    not isinstance(track_id, str)
                    or not 1 <= len(track_id.strip()) <= 100
                    or not isinstance(artists, list)
                    or not artists
                ):
                    return None
                track_ids.add(track_id.strip())
                for artist in artists:
                    if not isinstance(artist, dict) or not isinstance(artist.get("name"), str):
                        return None
                    normalized = self._normalize(artist["name"])
                    if not normalized:
                        return None
                    artist_names.add(normalized)
            return frozenset(track_ids), frozenset(artist_names)

        track_ids, artist_names = self._cached_personalization(
            access_token,
            "recently_played",
            load,
            (frozenset(), frozenset()),
        )
        return set(track_ids), set(artist_names)

    def _cached_personalization(
        self,
        access_token: str,
        signal: str,
        loader: Callable[[], _PersonalizationValue | None],
        default: _PersonalizationValue,
    ) -> _PersonalizationValue:
        scope: bytes | None = None
        try:
            scope = self.personalization_cache.scope_for(access_token)
            fresh = self.personalization_cache.get_fresh(scope, signal)
            if fresh is not None:
                return fresh
        except Exception:
            # Cache failure must never block the deterministic catalog path.
            scope = None
        try:
            value = loader()
        except Exception:
            value = None
        if value is not None:
            if scope is not None:
                try:
                    self.personalization_cache.put(scope, signal, value)
                except Exception:
                    pass
            return value
        if scope is not None:
            try:
                stale = self.personalization_cache.get_stale(scope, signal)
            except Exception:
                stale = None
            if stale is not None:
                return stale
        return default

    @classmethod
    def _has_explicit_chinese_artist_track_shape(
        cls,
        source_text: str | None,
        artist: str | None,
        track: str,
    ) -> bool:
        """Require the original parser-shaped utterance before labeling a split risk."""

        if not source_text or not artist or not track:
            return False
        source = cls._compact_normalized(source_text)
        artist_key = cls._compact_normalized(artist)
        track_key = cls._compact_normalized(track)
        for prefix in ("spotify播放", "播放"):
            if source.startswith(prefix):
                return source[len(prefix) :] == f"{artist_key}的{track_key}"
        return False

    @staticmethod
    def _compact_normalized(value: str) -> str:
        return normalize_chinese_text(value).replace(" ", "")

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
        artist_ids = tuple(
            (
                artist.get("id", "").strip()
                if isinstance(artist, dict)
                and isinstance(artist.get("id"), str)
                and re.fullmatch(r"[A-Za-z0-9._~-]{1,128}", artist["id"].strip())
                else None
            )
            for artist in artists
            if isinstance(artist, dict) and str(artist.get("name", "")).strip()
        )
        try:
            return SpotifyTrackRef(
                track_id=str(item.get("id", "")).strip(),
                track_uri=str(item.get("uri", "")).strip(),
                track_name=str(item.get("name", "")).strip(),
                artist_names=names,
                artist_ids=artist_ids,
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
