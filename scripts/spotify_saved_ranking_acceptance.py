"""Read-only real-account acceptance probe for saved Spotify ranking.

The probe intentionally exposes only display labels and aggregate evidence. It
does not enumerate the user's Library, start playback, or call any Library
write endpoint. Use SPOTIFY_TOKEN_PATH to point at the local Agent token store
when running it from a source checkout.
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


def _label(track: SpotifyTrackRef) -> str:
    artists = "、".join(track.artist_names)
    album = f"（專輯：{track.album_name}）" if track.album_name else ""
    return f"{artists} — {track.track_name}{album}"


def _titles_from_args() -> tuple[str, ...]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--title",
        action="append",
        dest="titles",
        help="Additional bare song title to search; it is used only as Spotify search text.",
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
    return titles


def main() -> int:
    titles = _titles_from_args()
    config = load_config()
    token = SpotifyTokenStore(config.spotify_token_file).load()
    if token is None:
        _emit({"status": "blocked", "reason": "spotify_token_missing"})
        return 2
    if token.expires_at <= time.time() + 60:
        _emit({"status": "blocked", "reason": "spotify_access_token_expired"})
        return 2
    if "user-library-read" not in set(token.scope.split()):
        _emit({"status": "blocked", "reason": "user_library_read_scope_missing"})
        return 2

    transport = SpotifyApiClient()
    client = ReadOnlyRecordingClient(transport)
    catalog = SpotifyCatalog(client)
    ambiguous_cases = 0
    saved_memberships = 0
    api_errors = 0
    accepted_cases: list[dict] = []

    try:
        for title in titles:
            try:
                result = catalog.find_track(title, None, access_token=token.access_token)
            except SpotifyApiError as exc:
                api_errors += 1
                _emit({"status": "search_error", "title": title, "status_code": exc.status_code})
                continue

            if not result.ambiguous or result.track is not None:
                continue
            ambiguous_cases += 1
            if not result.candidates or not client.saved_batches or not client.searches:
                continue

            saved_batch = client.saved_batches[-1]
            if len(saved_batch) > 3 or any(track.track_uri not in saved_batch for track in result.candidates):
                _emit({"status": "blocked", "reason": "candidate_boundary_violation", "title": title})
                return 4
            if len(client.saved_results) < len(client.saved_batches):
                continue
            saved_statuses = client.saved_results[-1]
            if len(saved_statuses) != len(saved_batch) or any(not isinstance(value, bool) for value in saved_statuses):
                _emit({"status": "blocked", "reason": "malformed_library_membership", "title": title})
                return 4
            saved_by_uri = dict(zip(saved_batch, saved_statuses))
            saved_memberships += sum(1 for value in saved_statuses if value)

            raw_refs = []
            for item in client.searches[-1]:
                ref = catalog._to_ref(item)
                if ref is not None and catalog._classify_version(ref) != "live":
                    raw_refs.append(ref)
            if not raw_refs:
                continue
            first = result.candidates[0]
            raw_position = next(
                (index for index, ref in enumerate(raw_refs) if ref.track_uri == first.track_uri),
                None,
            )
            if saved_by_uri.get(first.track_uri, False) and raw_position is not None and raw_position > 0:
                accepted_cases.append(
                    {
                        "title": title,
                        "ambiguous": True,
                        "raw_first": _label(raw_refs[0]),
                        "saved_first": _label(first),
                        "options": [_label(candidate) for candidate in result.candidates],
                        "library_batch_size": len(saved_batch),
                    }
                )
    finally:
        transport.close()

    if accepted_cases:
        _emit(
            {
                "status": "accepted",
                "cases": accepted_cases,
                "ambiguous_cases": ambiguous_cases,
                "saved_memberships": saved_memberships,
                "library_errors": client.saved_errors,
                "api_errors": api_errors,
                "writes_performed": False,
                "playback_performed": False,
            }
        )
        return 0

    _emit(
        {
            "status": "blocked",
            "reason": "no_saved_candidate_reordered_from_original_search_order",
            "ambiguous_cases": ambiguous_cases,
            "saved_memberships": saved_memberships,
            "library_errors": client.saved_errors,
            "api_errors": api_errors,
            "writes_performed": False,
            "playback_performed": False,
        }
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
