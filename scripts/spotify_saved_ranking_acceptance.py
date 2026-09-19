"""Read-only real-account acceptance probe for saved Spotify ranking.

The probe never enumerates the user's Library, starts playback, or calls a
Library write endpoint. Account track and artist names stay in memory; emitted
results contain aggregate evidence and case numbers only. Use
SPOTIFY_TOKEN_PATH to point at the local Agent token store when running it from
a source checkout.
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
    """Expose only the two read operations needed by the saved slice."""

    def __init__(self, client: SpotifyApiClient) -> None:
        self.client = client
        self.searches: list[list[dict]] = []
        self.saved_batches: list[tuple[str, ...]] = []
        self.saved_results: list[list[bool]] = []
        self.saved_errors = 0

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
    token_scopes = set(token.scope.split())
    if "user-library-read" not in token_scopes:
        _emit({"status": "blocked", "reason": "user_library_read_scope_missing"})
        return 2
    if from_recent and "user-read-recently-played" not in token_scopes:
        _emit({"status": "blocked", "reason": "user_read_recently_played_scope_missing"})
        return 2

    transport = SpotifyApiClient()
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

    client = ReadOnlyRecordingClient(transport)
    catalog = SpotifyCatalog(client)
    ambiguous_cases = 0
    saved_memberships = 0
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
                or len(set(saved_batch)) != len(saved_batch)
                or set(saved_batch) != set(candidate_uris)
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
            first = candidates[0]
            raw_position = raw_positions.get(first.track_uri)
            if saved_by_uri.get(first.track_uri, False) and raw_position is not None and raw_position > 0:
                accepted_cases.append(
                    {
                        "case_number": len(accepted_cases) + 1,
                        "original_position": raw_position,
                        "final_position": 0,
                        "ambiguous": True,
                        "ambiguity_preserved": True,
                        "library_batch_size": len(saved_batch),
                    }
                )
    finally:
        transport.close()

    common = {
        "ambiguous_cases": ambiguous_cases,
        "saved_memberships": saved_memberships,
        "library_errors": client.saved_errors,
        "api_errors": api_errors,
        "writes_performed": False,
        "playback_performed": False,
        "seeded_recent_title_count": seeded_recent_title_count,
    }
    if accepted_cases and not any(common[key] > 0 for key in ("api_errors", "library_errors")):
        _emit(
            {
                "status": "accepted",
                "cases": accepted_cases,
                **common,
            }
        )
        return 0

    reason = (
        "lookup_errors_prevented_saved_signal_isolation"
        if any(common[key] > 0 for key in ("api_errors", "library_errors"))
        else "no_saved_candidate_reordered_from_original_search_order"
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
