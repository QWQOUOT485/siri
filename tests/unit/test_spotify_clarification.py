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
