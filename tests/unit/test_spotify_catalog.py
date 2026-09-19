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


def track(track_id, name, artists, album="Album", *, isrc=None, duration_ms=None, album_type=None):
    payload = {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "artists": [{"name": artist} for artist in artists],
        "album": {"name": album},
    }
    if isrc is not None:
        payload["external_ids"] = {"isrc": isrc}
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if album_type is not None:
        payload["album"]["album_type"] = album_type
    return payload


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


def test_catalog_prefers_canonical_studio_over_live_for_same_artist():
    client = FakeSpotifySearchClient(
        [
            track("live", "晴天", ["周杰倫"], album="2004 無與倫比演唱會"),
            track("studio", "晴天", ["周杰倫"], album="葉惠美"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰倫", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "studio"
    assert result.ambiguous is False


def test_catalog_excludes_live_candidates_when_no_formal_recording_exists():
    client = FakeSpotifySearchClient(
        [
            track("live", "晴天", ["周杰倫"], album="2004 無與倫比演唱會"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰倫", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is False
    assert result.candidates == ()


def test_catalog_rejects_explicit_live_intent_without_searching():
    client = FakeSpotifySearchClient(
        [
            track("studio", "晴天", ["周杰倫"], album="葉惠美"),
            track("live", "晴天", ["周杰倫"], album="2004 無與倫比演唱會"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰倫", version_hint="live", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is False
    assert result.candidates == ()
    assert client.queries == []


def test_catalog_uses_original_as_ranking_intent_not_a_free_text_query():
    client = FakeSpotifySearchClient(
        [
            track("live", "晴天", ["周杰倫"], album="2004 無與倫比演唱會"),
            track("studio", "晴天", ["周杰倫"], album="葉惠美"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰倫", version_hint="original", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "studio"
    assert client.queries == [("test-token", "track:晴天 artist:周杰倫", 10)]


def test_catalog_rejects_explicit_live_without_search_even_if_multiple_versions_exist():
    client = FakeSpotifySearchClient(
        [
            track("liveone", "晴天", ["周杰倫"], album="2004 無與倫比演唱會"),
            track("livetwo", "晴天", ["周杰倫"], album="地表最強世界巡迴演唱會"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰倫", version_hint="live", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is False
    assert result.candidates == ()
    assert client.queries == []


def test_catalog_does_not_choose_between_different_artists_for_bare_title():
    client = FakeSpotifySearchClient(
        [
            track("one", "Stay", ["Artist One"], album="Studio"),
            track("two", "Stay", ["Artist Two"], album="Studio"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_limits_ambiguous_candidates_to_three():
    client = FakeSpotifySearchClient(
        [track(str(index), "Stay", ["The Kid LAROI"], album=f"Album {index}") for index in range(5)]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert len(result.candidates) == 3


def test_catalog_can_collapse_same_recording_releases_when_isrc_matches():
    client = FakeSpotifySearchClient(
        [
            track("original", "Stay", ["The Kid LAROI"], album="Album", isrc="USABC2400001"),
            track("release", "Stay", ["The Kid LAROI"], album="Another Release", isrc="USABC2400001"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "original"
    assert result.ambiguous is False


def test_catalog_normalizes_traditional_simplified_identity_metadata():
    client = FakeSpotifySearchClient(
        [
            track("original", "晴天", ["周杰倫"], album="葉惠美", isrc="TWABC2400001"),
            track("release", "晴天", ["周杰伦"], album="叶惠美", isrc="TWABC2400001"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰伦", "叶惠美", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "original"
    assert result.ambiguous is False


def test_catalog_does_not_use_duration_alone_to_guess_a_recording():
    client = FakeSpotifySearchClient(
        [
            track("one", "Stay", ["The Kid LAROI"], album="Album One", duration_ms=180000),
            track("two", "Stay", ["The Kid LAROI"], album="Album Two", duration_ms=180000),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True


def test_catalog_uses_album_hint_to_select_the_requested_release():
    client = FakeSpotifySearchClient(
        [
            track("live", "晴天", ["周杰倫"], album="2004 Live"),
            track("studio", "晴天", ["周杰倫"], album="葉惠美"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("晴天", "周杰倫", "葉惠美", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "studio"
    assert client.queries == [("test-token", "track:晴天 artist:周杰倫 album:葉惠美", 10)]


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


def test_catalog_retries_bare_chinese_title_when_de_separator_was_misparsed_as_artist():
    class StagedClient:
        def __init__(self):
            self.queries = []

        def search_tracks(self, access_token, query, *, limit=10):
            self.queries.append((access_token, query, limit))
            if query == "track:終點 artist:死亡是生命":
                return []
            if query == "track:死亡是生命的終點":
                return [track("deathend", "死亡是生命的終點", ["Sasi"], album="納薩力克")]
            raise AssertionError(query)

    client = StagedClient()
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("終點", "死亡是生命", access_token="test-token")

    assert result.track is not None
    assert result.track.track_id == "deathend"
    assert result.track.track_name == "死亡是生命的終點"
    assert client.queries == [
        ("test-token", "track:終點 artist:死亡是生命", 10),
        ("test-token", "track:死亡是生命的終點", 10),
    ]


def test_catalog_prefers_one_exact_bare_title_over_similar_titles():
    class StagedClient:
        def search_tracks(self, access_token, query, *, limit=10):
            if query == "track:終點 artist:死亡是生命":
                return []
            if query == "track:死亡是生命的終點":
                return [
                    track("exacttitle", "死亡是生命的終點", ["SASIOVERLXRD"], album="納薩力克"),
                    track("nearone", "死亡不是生命的終點", ["SASIOVERLXRD"], album="納薩力克"),
                    track("neartwo", "死亡到底是不是生命的终点", ["BreakuU"], album="无间道"),
                ]
            raise AssertionError(query)

    result = SpotifyCatalog(StagedClient()).find_track(
        "終點",
        "死亡是生命",
        access_token="test-token",
    )

    assert result.track is not None
    assert result.track.track_id == "exacttitle"
    assert result.ambiguous is False
