import pytest
from pydantic import ValidationError

from app.adapters.spotify.catalog import SpotifyCatalog, SpotifyTrackRef


class FakeSpotifySearchClient:
    def __init__(self, tracks):
        self.tracks = tracks
        self.queries = []

    def search_tracks(self, access_token, query, *, limit=10):
        self.queries.append((access_token, query, limit))
        return self.tracks


def track(track_id, name, artists, album="Album"):
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "artists": [{"name": artist} for artist in artists],
        "album": {"name": album},
    }


def test_catalog_returns_exact_track_and_artist_as_trusted_reference():
    client = FakeSpotifySearchClient(
        [
            track("wrong", "Stay", ["Other Artist"]),
            track("right", "Stay", ["The Kid LAROI"]),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "right"
    assert result.track.track_uri == "spotify:track:right"
    assert client.queries == [("test-token", "track:Stay artist:The Kid LAROI", 10)]


def test_catalog_refuses_to_choose_between_close_candidates():
    client = FakeSpotifySearchClient(
        [
            track("one", "Stay", ["The Kid LAROI"]),
            track("two", "Stay", ["The Kid LAROI"]),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_reports_no_results_without_creating_a_playable_reference():
    catalog = SpotifyCatalog(FakeSpotifySearchClient([]))

    result = catalog.find_track("Missing Song", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is False
    assert result.candidates == ()


def test_track_reference_rejects_client_controlled_non_spotify_uri():
    with pytest.raises(ValidationError):
        SpotifyTrackRef(
            track_id="evil",
            track_uri="https://evil.example/play",
            track_name="Not Trusted",
            artist_names=("Unknown",),
            album_name="Unknown",
        )
