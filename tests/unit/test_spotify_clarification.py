from concurrent.futures import ThreadPoolExecutor

import pytest

from app.adapters.spotify.catalog import SpotifyTrackRef
from app.services.spotify_clarification import SpotifyClarificationStore


def candidate(track_id: str, artist: str, album: str) -> SpotifyTrackRef:
    return SpotifyTrackRef(
        track_id=track_id,
        track_uri=f"spotify:track:{track_id}",
        track_name="Stay",
        artist_names=(artist,),
        album_name=album,
    )


def test_store_accepts_only_at_most_three_server_candidates():
    store = SpotifyClarificationStore()
    tracks = [candidate(str(index), f"Artist {index}", f"Album {index}") for index in range(4)]

    with pytest.raises(ValueError):
        store.create(tracks)


def test_store_reports_expired_context_and_rejects_replay():
    now = [100.0]
    store = SpotifyClarificationStore(clock=lambda: now[0])
    token = store.create([candidate("one", "Artist One", "Album One")])

    now[0] += 60
    expired = store.select(token, "第一首")

    assert expired.track is None
    assert expired.error_code == "SPOTIFY_CLARIFICATION_EXPIRED"
    replay = store.select(token, "第一首")
    assert replay.error_code == "SPOTIFY_CLARIFICATION_INVALID"


def test_store_selection_is_limited_to_the_trusted_set():
    store = SpotifyClarificationStore()
    token = store.create(
        [
            candidate("one", "Artist One", "Album One"),
            candidate("two", "Artist Two", "Album Two"),
        ]
    )

    selected = store.select(token, "Album Two")

    assert selected.track is not None
    assert selected.track.track_id == "two"


def test_store_accepts_simplified_ordinal_follow_up():
    store = SpotifyClarificationStore()
    token = store.create(
        [
            candidate("one", "Artist One", "Album One"),
            candidate("two", "Artist Two", "Album Two"),
        ]
    )

    selected = store.select(token, "第二个")

    assert selected.track is not None
    assert selected.track.track_id == "two"


def test_store_invalidates_context_after_three_unclear_attempts():
    store = SpotifyClarificationStore(max_attempts=3)
    token = store.create(
        [
            candidate("one", "Artist One", "Album One"),
            candidate("two", "Artist Two", "Album Two"),
        ]
    )

    first = store.select(token, "那一首")
    second = store.select(token, "還是不知道")
    exhausted = store.select(token, "隨便一首")

    assert first.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert first.clarification_token == token
    assert second.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert second.clarification_token == token
    assert exhausted.error_code == "SPOTIFY_CLARIFICATION_ATTEMPTS_EXHAUSTED"
    assert exhausted.clarification_token is None
    assert store.select(token, "第一首").error_code == "SPOTIFY_CLARIFICATION_USED"


def test_store_allows_only_one_concurrent_successful_selection():
    store = SpotifyClarificationStore()
    token = store.create(
        [
            candidate("one", "Artist One", "Album One"),
            candidate("two", "Artist Two", "Album Two"),
        ]
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: store.select(token, "第一首"), range(8)))

    successes = [result for result in results if result.track is not None]
    failures = [result for result in results if result.track is None]

    assert len(successes) == 1
    assert successes[0].track.track_id == "one"
    assert len(failures) == 7
    assert all(result.error_code == "SPOTIFY_CLARIFICATION_USED" for result in failures)


def test_store_bounds_concurrent_unclear_attempts_atomically():
    store = SpotifyClarificationStore(max_attempts=3)
    token = store.create(
        [
            candidate("one", "Artist One", "Album One"),
            candidate("two", "Artist Two", "Album Two"),
        ]
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: store.select(token, "不知道"), range(8)))

    error_codes = [result.error_code for result in results]
    assert error_codes.count("SPOTIFY_CLARIFICATION_UNCLEAR") == 2
    assert error_codes.count("SPOTIFY_CLARIFICATION_ATTEMPTS_EXHAUSTED") == 1
    assert error_codes.count("SPOTIFY_CLARIFICATION_USED") == 5
