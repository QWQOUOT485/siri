"""Read-only real-account acceptance probe for Spotify Recently Played ranking.

The probe never enumerates the user's Library, starts playback, or calls a
Library write endpoint. It accepts a case only when a real Recently Played
track/artist signal reorders an existing genuine-ambiguity candidate set while
saved and Top Tracks/Artists signals are absent for that set.

Use SPOTIFY_TOKEN_PATH to point at the local Agent token store when running it
from a source checkout. Account track and artist names are kept in memory only;
the emitted result contains aggregate evidence and case numbers only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.adapters.spotify.catalog import SpotifyCatalog, SpotifyTrackRef
from app.adapters.spotify.client import SpotifyApiClient, SpotifyApiError
from app.infrastructure.config import load_config
from app.infrastructure.spotify_auth import SpotifyTokenStore


DEFAULT_TITLES = (
    "後來",
    "晴天",
    "小幸運",
    "演員",
    "成全",
    "如果可以",
    "稻香",
    "告白氣球",
    "起風了",
    "突然好想你",
    "童話",
    "光年之外",
    "年少有為",
    "我懷念的",
    "Stay",
    "Hello",
    "Numb",
    "Havana",
    "Attention",
    "Shape of You",
)


class ReadOnlyRecordingClient:
    """Expose and cache only the bounded read operations used by the slice."""

    def __init__(self, client: SpotifyApiClient) -> None:
        self.client = client
        self.searches: list[list[dict]] = []
        self.saved_batches: list[tuple[str, ...]] = []
        self.saved_results: list[list[bool]] = []
        self.saved_errors = 0
        self.top_track_items: list[dict] | None = None
        self.top_artist_items: list[dict] | None = None
        self.recent_items: list[dict] | None = None
        self.top_track_errors = 0
        self.top_artist_errors = 0
        self.recent_errors = 0
        self._top_track_error: SpotifyApiError | None = None
        self._top_artist_error: SpotifyApiError | None = None
        self._recent_error: SpotifyApiError | None = None

    def search_tracks(self, access_token: str, query: str, *, limit: int = 10) -> list[dict]:
        payload = self.client.search_tracks(access_token, query, limit=limit)
        self.searches.append(payload)
        return payload

    def check_saved_tracks(self, access_token: str, track_uris: tuple[str, ...]) -> list[bool]:
        self.saved_batches.append(tuple(track_uris))
        try:
            statuses = self.client.check_saved_tracks(access_token, track_uris)
        except SpotifyApiError:
            self.saved_errors += 1
            raise
        self.saved_results.append(statuses)
        return statuses

    def get_top_tracks(self, access_token: str, *, limit: int = 50) -> list[dict]:
        if self._top_track_error is not None:
            raise self._top_track_error
        if self.top_track_items is None:
            try:
                self.top_track_items = self.client.get_top_tracks(access_token, limit=limit)
            except SpotifyApiError as exc:
                self._top_track_error = exc
                self.top_track_errors += 1
                raise
        return list(self.top_track_items)

    def get_top_artists(self, access_token: str, *, limit: int = 50) -> list[dict]:
        if self._top_artist_error is not None:
            raise self._top_artist_error
        if self.top_artist_items is None:
            try:
                self.top_artist_items = self.client.get_top_artists(access_token, limit=limit)
            except SpotifyApiError as exc:
                self._top_artist_error = exc
                self.top_artist_errors += 1
                raise
        return list(self.top_artist_items)

    def get_recently_played(self, access_token: str, *, limit: int = 50) -> list[dict]:
        if self._recent_error is not None:
            raise self._recent_error
        if self.recent_items is None:
            try:
                self.recent_items = self.client.get_recently_played(access_token, limit=limit)
            except SpotifyApiError as exc:
                self._recent_error = exc
                self.recent_errors += 1
                raise
        return list(self.recent_items)


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def _titles_from_args() -> tuple[tuple[str, ...], bool]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--title",
        action="append",
        dest="titles",
        help="Additional bare song title to search; it is used only as Spotify search text.",
    )
    parser.add_argument(
        "--from-recent",
        action="store_true",
        help="Add a bounded, in-memory sample of Recently Played titles to the probe.",
    )
    args = parser.parse_args()
    titles = tuple(args.titles or DEFAULT_TITLES)
    if not titles:
        parser.error("at least one title is required")
    for title in titles:
        if not isinstance(title, str) or not 0 < len(title.strip()) <= 100:
            parser.error("each title must contain 1 to 100 characters")
        if any(ord(char) < 32 or ord(char) == 127 for char in title):
            parser.error("titles must not contain control characters")
    return titles, args.from_recent


def _raw_refs_for_candidates(
    catalog: SpotifyCatalog,
    payloads: list[list[dict]],
    candidate_uris: set[str],
) -> list[SpotifyTrackRef]:
    for payload in reversed(payloads):
        refs = [
            ref
            for item in payload
            if (ref := catalog._to_ref(item)) is not None and catalog._classify_version(ref) != "live"
        ]
        if any(ref.track_uri in candidate_uris for ref in refs):
            return refs
    return []


def _recent_signals(catalog: SpotifyCatalog, items: list[dict] | None) -> tuple[set[str], set[str]]:
    if items is None:
        return set(), set()
    track_ids: set[str] = set()
    artist_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        track = item.get("track") if "track" in item else item
        if not isinstance(track, dict):
            continue
        track_id = track.get("id")
        if isinstance(track_id, str) and track_id.strip():
            track_ids.add(track_id.strip())
        artists = track.get("artists")
        if isinstance(artists, list):
            for artist in artists:
                if isinstance(artist, dict) and isinstance(artist.get("name"), str):
                    normalized = catalog._normalize(artist["name"])
                    if normalized:
                        artist_names.add(normalized)
    return track_ids, artist_names


def _recent_titles(items: list[dict]) -> tuple[str, ...]:
    titles: list[str] = []
    for item in items:
        track = item.get("track") if isinstance(item, dict) else None
        if not isinstance(track, dict):
            continue
        title = track.get("name")
        if (
            isinstance(title, str)
            and 0 < len(title.strip()) <= 100
            and all(ord(char) >= 32 and ord(char) != 127 for char in title)
        ):
            titles.append(title.strip())
    return tuple(titles)


def main() -> int:
    titles, from_recent = _titles_from_args()
    config = load_config()
    token = SpotifyTokenStore(config.spotify_token_file).load()
    if token is None:
        _emit({"status": "blocked", "reason": "spotify_token_missing"})
        return 2
    if token.expires_at <= time.time() + 60:
        _emit({"status": "blocked", "reason": "spotify_access_token_expired"})
        return 2
    required_scopes = {"user-library-read", "user-top-read", "user-read-recently-played"}
    missing_scopes = sorted(required_scopes - set(token.scope.split()))
    if missing_scopes:
        _emit({"status": "blocked", "reason": "required_personalization_scope_missing", "missing_scopes": missing_scopes})
        return 2

    transport = SpotifyApiClient()
    client = ReadOnlyRecordingClient(transport)
    seeded_recent_title_count = 0
    if from_recent:
        try:
            recent_items = transport.get_recently_played(token.access_token, limit=50)
        except SpotifyApiError as exc:
            transport.close()
            _emit({"status": "blocked", "reason": "recently_played_lookup_failed", "status_code": exc.status_code})
            return 2
        recent_titles = _recent_titles(recent_items)
        titles = tuple(dict.fromkeys((*titles, *recent_titles)))
        seeded_recent_title_count = len(recent_titles)
        client.recent_items = recent_items

    catalog = SpotifyCatalog(client)
    ambiguous_cases = 0
    raw_candidate_sets = 0
    saved_memberships = 0
    top_track_matches = 0
    top_artist_matches = 0
    recent_matches = 0
    api_errors = 0
    accepted_cases: list[dict] = []

    try:
        for title in titles:
            search_start = len(client.searches)
            saved_start = len(client.saved_results)
            try:
                result = catalog.find_track(title, None, access_token=token.access_token)
            except SpotifyApiError as exc:
                api_errors += 1
                _emit({"status": "search_error", "status_code": exc.status_code})
                continue

            if not result.ambiguous or result.track is not None:
                continue
            ambiguous_cases += 1
            candidates = tuple(result.candidates)
            if len(candidates) < 2 or len(client.saved_results) <= saved_start:
                continue

            saved_batch = client.saved_batches[-1]
            saved_statuses = client.saved_results[-1]
            candidate_uris = tuple(candidate.track_uri for candidate in candidates)
            if (
                len(saved_batch) > 3
                or saved_batch != candidate_uris
                or len(saved_statuses) != len(saved_batch)
                or any(not isinstance(value, bool) for value in saved_statuses)
            ):
                _emit({"status": "blocked", "reason": "malformed_library_membership"})
                return 4
            saved_by_uri = dict(zip(saved_batch, saved_statuses))
            saved_memberships += sum(1 for value in saved_statuses if value)

            raw_refs = _raw_refs_for_candidates(
                catalog,
                client.searches[search_start:],
                set(candidate_uris),
            )
            raw_positions = {ref.track_uri: index for index, ref in enumerate(raw_refs)}
            raw_candidates = [candidate for candidate in candidates if candidate.track_uri in raw_positions]
            raw_candidates.sort(key=lambda candidate: raw_positions[candidate.track_uri])
            if len(raw_candidates) < 2:
                continue
            raw_candidate_sets += 1

            top_track_ids = {
                item["id"].strip()
                for item in (client.top_track_items or [])
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
            }
            top_artist_names = {
                catalog._normalize(item["name"])
                for item in (client.top_artist_items or [])
                if isinstance(item, dict) and isinstance(item.get("name"), str) and catalog._normalize(item["name"])
            }
            recent_track_ids, recent_artist_names = _recent_signals(catalog, client.recent_items)

            def top_track_match(candidate: SpotifyTrackRef) -> bool:
                return candidate.track_id in top_track_ids

            def top_artist_match(candidate: SpotifyTrackRef) -> bool:
                return any(catalog._normalize(name) in top_artist_names for name in candidate.artist_names)

            def recent_track_match(candidate: SpotifyTrackRef) -> bool:
                return candidate.track_id in recent_track_ids

            def recent_artist_match(candidate: SpotifyTrackRef) -> bool:
                return any(catalog._normalize(name) in recent_artist_names for name in candidate.artist_names)

            for candidate in candidates:
                if top_track_match(candidate):
                    top_track_matches += 1
                if top_artist_match(candidate):
                    top_artist_matches += 1
                if recent_track_match(candidate) or recent_artist_match(candidate):
                    recent_matches += 1

            raw_first = raw_candidates[0]
            final_first = candidates[0]
            if final_first.track_uri == raw_first.track_uri or final_first.track_uri not in raw_positions:
                continue
            if any(saved_by_uri.get(candidate.track_uri, False) for candidate in candidates):
                continue
            if any(top_track_match(candidate) or top_artist_match(candidate) for candidate in candidates):
                continue

            final_recent_track = recent_track_match(final_first)
            final_recent_artist = recent_artist_match(final_first)
            raw_recent = recent_track_match(raw_first) or recent_artist_match(raw_first)
            if not (final_recent_track or final_recent_artist) or raw_recent:
                continue
            accepted_cases.append(
                {
                    "case_number": len(accepted_cases) + 1,
                    "signal": "recent_track" if final_recent_track else "recent_artist",
                    "original_position": raw_positions[final_first.track_uri],
                    "final_position": 0,
                    "ambiguity_preserved": True,
                }
            )
    finally:
        transport.close()

    common = {
        "ambiguous_cases": ambiguous_cases,
        "raw_candidate_sets": raw_candidate_sets,
        "saved_memberships": saved_memberships,
        "top_track_matches": top_track_matches,
        "top_artist_matches": top_artist_matches,
        "recent_matches": recent_matches,
        "api_errors": api_errors,
        "library_errors": client.saved_errors,
        "top_track_errors": client.top_track_errors,
        "top_artist_errors": client.top_artist_errors,
        "recent_errors": client.recent_errors,
        "writes_performed": False,
        "playback_performed": False,
        "seeded_recent_title_count": seeded_recent_title_count,
    }
    if accepted_cases and not any(
        (common[key] > 0 for key in ("api_errors", "library_errors", "top_track_errors", "top_artist_errors", "recent_errors"))
    ):
        _emit({"status": "accepted", "cases": accepted_cases, **common})
        return 0

    reason = (
        "lookup_errors_prevented_signal_isolation"
        if any(common[key] > 0 for key in ("api_errors", "library_errors", "top_track_errors", "top_artist_errors", "recent_errors"))
        else "no_recent_candidate_reordered_from_original_search_order_without_stronger_signal"
    )
    _emit({"status": "blocked", "reason": reason, **common})
    return 3


if __name__ == "__main__":
    sys.exit(main())
