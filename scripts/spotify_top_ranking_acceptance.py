"""Read-only real-account acceptance probe for Spotify Top ranking.

The probe never enumerates the user's Library, starts playback, or calls a
Library write endpoint. It accepts a case only when a real Top Track/Artist
signal reorders an existing genuine-ambiguity candidate set while saved and
Recently Played signals are absent for that set.
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

MAX_TOP_ARTIST_SEEDS = 50
MAX_TOP_ARTIST_TITLES = 50
TOP_ARTIST_TRACKS_PER_SEED = 1
MAX_PROBE_RETRY_WAIT_SECONDS = 30


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
        self.top_track_error: SpotifyApiError | None = None
        self.top_artist_error: SpotifyApiError | None = None
        self.recent_error: SpotifyApiError | None = None
        self.rate_limit_errors = 0
        self.rate_limit_reasons: set[str] = set()
        self.last_retry_after_seconds: int | None = None
        self.rate_limit_retry_used = False
        self.rate_limit_exhausted = False

    def _record_rate_limit(self, error: SpotifyApiError) -> None:
        self.rate_limit_errors += 1
        if error.reason is not None:
            self.rate_limit_reasons.add(error.reason)
        self.last_retry_after_seconds = error.retry_after_seconds

    def rate_limit_summary(self) -> dict:
        summary = {
            "rate_limit_errors": self.rate_limit_errors,
            "rate_limit_retry_used": self.rate_limit_retry_used,
            "rate_limit_exhausted": self.rate_limit_exhausted,
            "rate_limit_reasons": sorted(self.rate_limit_reasons),
        }
        if self.last_retry_after_seconds is not None:
            summary["last_retry_after_seconds"] = self.last_retry_after_seconds
        return summary

    def _call(self, operation):
        try:
            return operation()
        except SpotifyApiError as exc:
            if exc.status_code != 429:
                raise
            self._record_rate_limit(exc)
            if (
                self.rate_limit_retry_used
                or exc.reason == "QUOTA_EXCEEDED"
                or exc.retry_after_seconds is None
                or exc.retry_after_seconds > MAX_PROBE_RETRY_WAIT_SECONDS
            ):
                self.rate_limit_exhausted = True
                raise
            self.rate_limit_retry_used = True
            time.sleep(exc.retry_after_seconds)
            try:
                return operation()
            except SpotifyApiError as retry_exc:
                if retry_exc.status_code == 429:
                    self._record_rate_limit(retry_exc)
                    self.rate_limit_exhausted = True
                raise

    def search_seed_tracks(self, access_token: str, query: str, *, limit: int = 10) -> list[dict]:
        """Search only for corpus seeding without mixing it into acceptance evidence."""

        return self._call(lambda: self.client.search_tracks(access_token, query, limit=limit))

    def search_tracks(self, access_token: str, query: str, *, limit: int = 10) -> list[dict]:
        payload = self._call(lambda: self.client.search_tracks(access_token, query, limit=limit))
        self.searches.append(payload)
        return payload

    def check_saved_tracks(self, access_token: str, track_uris: tuple[str, ...]) -> list[bool]:
        self.saved_batches.append(tuple(track_uris))
        try:
            statuses = self._call(lambda: self.client.check_saved_tracks(access_token, track_uris))
        except SpotifyApiError:
            self.saved_errors += 1
            raise
        self.saved_results.append(statuses)
        return statuses

    def get_top_tracks(self, access_token: str, *, limit: int = 50) -> list[dict]:
        if self.top_track_error is not None:
            raise self.top_track_error
        if self.top_track_items is None:
            try:
                self.top_track_items = self._call(lambda: self.client.get_top_tracks(access_token, limit=limit))
            except SpotifyApiError as exc:
                self.top_track_error = exc
                raise
        return list(self.top_track_items)

    def get_top_artists(self, access_token: str, *, limit: int = 50) -> list[dict]:
        if self.top_artist_error is not None:
            raise self.top_artist_error
        if self.top_artist_items is None:
            try:
                self.top_artist_items = self._call(lambda: self.client.get_top_artists(access_token, limit=limit))
            except SpotifyApiError as exc:
                self.top_artist_error = exc
                raise
        return list(self.top_artist_items)

    def get_recently_played(self, access_token: str, *, limit: int = 50) -> list[dict]:
        if self.recent_error is not None:
            raise self.recent_error
        if self.recent_items is None:
            try:
                self.recent_items = self._call(lambda: self.client.get_recently_played(access_token, limit=limit))
            except SpotifyApiError as exc:
                self.recent_error = exc
                raise
        return list(self.recent_items)


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def _spotify_error_details(error: SpotifyApiError) -> dict:
    details = {"status_code": error.status_code}
    if error.retry_after_seconds is not None:
        details["retry_after_seconds"] = error.retry_after_seconds
    if error.reason is not None:
        details["spotify_reason"] = error.reason
    return details


def _titles_from_args() -> tuple[tuple[str, ...], bool, bool, bool, int]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--title",
        action="append",
        dest="titles",
        help="Additional bare song title to search; it is used only as Spotify search text.",
    )
    parser.add_argument(
        "--from-top-tracks",
        action="store_true",
        help="Add a bounded, in-memory sample of the account's Top Track titles to the probe.",
    )
    parser.add_argument(
        "--from-top-artists",
        action="store_true",
        help="Add a bounded, in-memory sample of titles found from the account's Top Artists to the probe.",
    )
    parser.add_argument(
        "--top-artist-only",
        action="store_true",
        help="Accept only a reorder caused by Top Artist, with no saved, Top Track, or Recently Played signal.",
    )
    parser.add_argument(
        "--top-artist-seed-limit",
        type=int,
        default=MAX_TOP_ARTIST_SEEDS,
        help=f"Bound the number of Top Artists used for corpus seeding (1-{MAX_TOP_ARTIST_SEEDS}).",
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
    if args.top_artist_only and not args.from_top_artists:
        parser.error("--top-artist-only requires --from-top-artists")
    if not 1 <= args.top_artist_seed_limit <= MAX_TOP_ARTIST_SEEDS:
        parser.error(f"--top-artist-seed-limit must be between 1 and {MAX_TOP_ARTIST_SEEDS}")
    return titles, args.from_top_tracks, args.from_top_artists, args.top_artist_only, args.top_artist_seed_limit


def _safe_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not 0 < len(value) <= 100 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    return value


def _top_artist_seed_titles(
    client: ReadOnlyRecordingClient,
    access_token: str,
    items: list[dict],
    *,
    artist_limit: int,
) -> tuple[str, ...]:
    """Build a bounded, in-memory bare-title corpus from Top Artist search results."""

    artist_names = tuple(
        dict.fromkeys(
            name
            for item in items[:artist_limit]
            if isinstance(item, dict)
            and (name := _safe_text(item.get("name"))) is not None
        )
    )
    titles: list[str] = []
    for artist_name in artist_names:
        payload = client.search_seed_tracks(
            access_token,
            f"artist:{artist_name}",
            limit=TOP_ARTIST_TRACKS_PER_SEED,
        )
        for item in payload:
            title = _safe_text(item.get("name")) if isinstance(item, dict) else None
            if title is not None:
                titles.append(title)
            if len(dict.fromkeys(titles)) >= MAX_TOP_ARTIST_TITLES:
                return tuple(dict.fromkeys(titles))[:MAX_TOP_ARTIST_TITLES]
    return tuple(dict.fromkeys(titles))[:MAX_TOP_ARTIST_TITLES]


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


def _top_track_ids(items: list[dict] | None) -> set[str]:
    if items is None:
        return set()
    return {
        item["id"].strip()
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    }


def _top_artist_names(catalog: SpotifyCatalog, items: list[dict] | None) -> set[str]:
    if items is None:
        return set()
    return {
        catalog._normalize(item["name"])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("name"), str) and catalog._normalize(item["name"])
    }


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


def main() -> int:
    titles, from_top_tracks, from_top_artists, top_artist_only, top_artist_seed_limit = _titles_from_args()
    config = load_config()
    token = SpotifyTokenStore(config.spotify_token_file).load()
    if token is None:
        _emit({"status": "blocked", "reason": "spotify_token_missing"})
        return 2
    if token.expires_at <= time.time() + 60:
        _emit({"status": "blocked", "reason": "spotify_access_token_expired"})
        return 2
    scopes = set(token.scope.split())
    missing_scopes = sorted({"user-library-read", "user-top-read", "user-read-recently-played"} - scopes)
    if missing_scopes:
        _emit({"status": "blocked", "reason": "required_personalization_scope_missing", "missing_scopes": missing_scopes})
        return 2

    transport = SpotifyApiClient()
    client = ReadOnlyRecordingClient(transport)
    seeded_top_title_count = 0
    seeded_top_artist_title_count = 0
    top_track_items: list[dict] | None = None
    top_artist_items: list[dict] | None = None
    if from_top_tracks:
        try:
            top_items = client.get_top_tracks(token.access_token, limit=50)
        except SpotifyApiError as exc:
            transport.close()
            _emit({"status": "blocked", "reason": "top_tracks_lookup_failed", **_spotify_error_details(exc), **client.rate_limit_summary()})
            return 2
        top_titles = tuple(
            item["name"].strip()
            for item in top_items
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and 0 < len(item["name"].strip()) <= 100
            and all(ord(char) >= 32 and ord(char) != 127 for char in item["name"])
        )
        titles = tuple(dict.fromkeys((*titles, *top_titles)))
        seeded_top_title_count = len(top_titles)
        top_track_items = top_items
    if from_top_artists:
        try:
            top_artist_items = client.get_top_artists(token.access_token, limit=50)
            top_artist_titles = _top_artist_seed_titles(
                client,
                token.access_token,
                top_artist_items,
                artist_limit=top_artist_seed_limit,
            )
        except SpotifyApiError as exc:
            transport.close()
            _emit({"status": "blocked", "reason": "top_artist_seed_lookup_failed", **_spotify_error_details(exc), **client.rate_limit_summary()})
            return 2
        titles = tuple(dict.fromkeys((*titles, *top_artist_titles)))
        seeded_top_artist_title_count = len(top_artist_titles)
    catalog = SpotifyCatalog(client)
    if top_track_items is not None:
        client.top_track_items = top_track_items
    if top_artist_items is not None:
        client.top_artist_items = top_artist_items
    ambiguous_cases = 0
    raw_candidate_sets = 0
    saved_memberships = 0
    top_track_matches = 0
    top_artist_matches = 0
    recent_matches = 0
    api_errors = 0
    accepted_cases: list[dict] = []
    top_artist_signal_cases = 0
    top_artist_only_opportunities = 0
    top_artist_only_reorders = 0
    top_artist_raw_first_matches = 0
    top_artist_final_first_matches = 0

    try:
        for title in titles:
            search_start = len(client.searches)
            saved_start = len(client.saved_results)
            try:
                result = catalog.find_track(title, None, access_token=token.access_token)
            except SpotifyApiError as exc:
                api_errors += 1
                if exc.status_code == 429:
                    _emit({"status": "blocked", "reason": "spotify_rate_limited", **_spotify_error_details(exc), **client.rate_limit_summary()})
                    return 2
                _emit({"status": "search_error", **_spotify_error_details(exc)})
                continue

            if client.rate_limit_exhausted:
                _emit({"status": "blocked", "reason": "spotify_rate_limited", **client.rate_limit_summary()})
                return 2

            if not result.ambiguous or result.track is not None:
                continue
            ambiguous_cases += 1
            candidates = tuple(result.candidates)
            if len(candidates) < 2 or len(client.saved_results) <= saved_start:
                continue

            saved_batch = client.saved_batches[-1]
            saved_statuses = client.saved_results[-1]
            if len(saved_batch) > 3 or len(saved_statuses) != len(saved_batch):
                _emit({"status": "blocked", "reason": "malformed_library_membership"})
                return 4
            if any(not isinstance(value, bool) for value in saved_statuses):
                _emit({"status": "blocked", "reason": "malformed_library_membership"})
                return 4
            saved_by_uri = dict(zip(saved_batch, saved_statuses))
            saved_memberships += sum(1 for value in saved_statuses if value)

            raw_refs = _raw_refs_for_candidates(
                catalog,
                client.searches[search_start:],
                {candidate.track_uri for candidate in candidates},
            )
            raw_positions = {ref.track_uri: index for index, ref in enumerate(raw_refs)}
            raw_candidates = [candidate for candidate in candidates if candidate.track_uri in raw_positions]
            raw_candidates.sort(key=lambda candidate: raw_positions[candidate.track_uri])
            if len(raw_candidates) < 2:
                continue
            raw_candidate_sets += 1

            top_track_ids = _top_track_ids(client.top_track_items)
            top_artist_names = _top_artist_names(catalog, client.top_artist_items)
            recent_track_ids, recent_artist_names = _recent_signals(catalog, client.recent_items)

            def top_track_match(candidate: SpotifyTrackRef) -> bool:
                return candidate.track_id in top_track_ids

            def top_artist_match(candidate: SpotifyTrackRef) -> bool:
                return any(catalog._normalize(name) in top_artist_names for name in candidate.artist_names)

            def recent_match(candidate: SpotifyTrackRef) -> bool:
                return candidate.track_id in recent_track_ids or any(
                    catalog._normalize(name) in recent_artist_names for name in candidate.artist_names
                )

            for candidate in candidates:
                if top_track_match(candidate):
                    top_track_matches += 1
                if top_artist_match(candidate):
                    top_artist_matches += 1
                if recent_match(candidate):
                    recent_matches += 1

            raw_first = raw_candidates[0]
            final_first = candidates[0]
            final_top_track = top_track_match(final_first)
            final_top_artist = top_artist_match(final_first)
            raw_top_track = top_track_match(raw_first)
            raw_top_artist = top_artist_match(raw_first)
            has_saved_signal = any(saved_by_uri.get(candidate.track_uri, False) for candidate in candidates)
            has_recent_signal = any(recent_match(candidate) for candidate in candidates)
            has_top_track_signal = any(top_track_match(candidate) for candidate in candidates)
            has_top_artist_signal = any(top_artist_match(candidate) for candidate in candidates)
            if has_top_artist_signal:
                top_artist_signal_cases += 1
            if has_top_artist_signal and not has_saved_signal and not has_recent_signal and not has_top_track_signal:
                top_artist_only_opportunities += 1
                if raw_top_artist:
                    top_artist_raw_first_matches += 1
                if final_top_artist:
                    top_artist_final_first_matches += 1
                if final_top_artist and not raw_top_artist:
                    top_artist_only_reorders += 1
            if final_first.track_uri == raw_first.track_uri or final_first.track_uri not in raw_positions:
                continue
            if any(saved_by_uri.get(candidate.track_uri, False) for candidate in candidates):
                continue
            if any(recent_match(candidate) for candidate in candidates):
                continue
            if top_artist_only and has_top_track_signal:
                continue
            if top_artist_only:
                if not final_top_artist or raw_top_artist or final_top_track or raw_top_track:
                    continue
                signal = "top_artist"
            else:
                if not (final_top_track or final_top_artist) or (raw_top_track or raw_top_artist):
                    continue
                signal = "top_track" if final_top_track else "top_artist"
            accepted_cases.append(
                {
                    "case_number": len(accepted_cases) + 1,
                    "signal": signal,
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
        "top_track_errors": int(client.top_track_error is not None),
        "top_artist_errors": int(client.top_artist_error is not None),
        "recent_errors": int(client.recent_error is not None),
        **client.rate_limit_summary(),
        "top_artist_signal_cases": top_artist_signal_cases,
        "top_artist_only_opportunities": top_artist_only_opportunities,
        "top_artist_only_reorders": top_artist_only_reorders,
        "top_artist_raw_first_matches": top_artist_raw_first_matches,
        "top_artist_final_first_matches": top_artist_final_first_matches,
        "writes_performed": False,
        "playback_performed": False,
        "seeded_top_title_count": seeded_top_title_count,
        "seeded_top_artist_title_count": seeded_top_artist_title_count,
        "top_artist_only": top_artist_only,
    }
    lookup_error_keys = (
        "api_errors",
        "library_errors",
        "top_track_errors",
        "top_artist_errors",
        "recent_errors",
        "rate_limit_errors",
    )
    if accepted_cases and not any(common[key] > 0 for key in lookup_error_keys):
        _emit({"status": "accepted", "cases": accepted_cases, **common})
        return 0

    reason = (
        "lookup_errors_prevented_signal_isolation"
        if any(common[key] > 0 for key in lookup_error_keys)
        else "no_top_candidate_reordered_from_original_search_order_without_stronger_signal"
    )
    _emit(
        {
            "status": "blocked",
            "reason": reason,
            **common,
        }
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
