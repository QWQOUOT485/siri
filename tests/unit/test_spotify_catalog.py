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


def track(
    track_id,
    name,
    artists,
    album="Album",
    *,
    isrc=None,
    duration_ms=None,
    album_type=None,
    popularity=None,
):
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
    if popularity is not None:
        payload["popularity"] = popularity
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


def test_catalog_uses_popularity_only_to_order_ambiguous_candidates():
    client = FakeSpotifySearchClient(
        [
            track("lesspopular", "Stay", ["The Kid LAROI"], album="Album One", popularity=20),
            track("morepopular", "Stay", ["The Kid LAROI"], album="Album Two", popularity=90),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["morepopular", "lesspopular"]


def test_catalog_uses_saved_status_to_order_ambiguous_candidates_without_auto_selecting():
    class PersonalizedClient(FakeSpotifySearchClient):
        def __init__(self, tracks):
            super().__init__(tracks)
            self.saved_calls = []

        def check_saved_tracks(self, access_token, track_uris):
            self.saved_calls.append((access_token, tuple(track_uris)))
            return [uri.endswith(":saved") for uri in track_uris]

    client = PersonalizedClient(
        [
            track("other", "Stay", ["The Kid LAROI"], album="Other Release"),
            track("saved", "Stay", ["The Kid LAROI"], album="Saved Release"),
        ]
    )
    catalog = SpotifyCatalog(client)

    result = catalog.find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["saved", "other"]
    assert client.saved_calls == [("test-token", ("spotify:track:other", "spotify:track:saved"))]


def test_catalog_saved_status_does_not_override_explicit_artist_relevance():
    class PersonalizedClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [uri.endswith(":weaker") for uri in track_uris]

    client = PersonalizedClient(
        [
            track("exact", "Stay", ["Artist One"]),
            track("weaker", "Stay", ["Artist Oner"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", "Artist One", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["exact", "weaker"]


def test_catalog_falls_back_to_deterministic_order_when_saved_lookup_is_unavailable():
    class UnavailableSavedClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, _track_uris):
            raise RuntimeError("library scope unavailable")

    client = UnavailableSavedClient(
        [
            track("one", "Stay", ["The Kid LAROI"]),
            track("two", "Stay", ["The Kid LAROI"]),
        ]
    )
    result = SpotifyCatalog(client).find_track("Stay", "The Kid LAROI", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_library_failure_skips_other_personalization_signals():
    class BrokenLibraryClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, _track_uris):
            raise RuntimeError("library scope unavailable")

        def get_top_tracks(self, _access_token):
            return [track("two", "Stay", ["Artist Two"])]

        def get_top_artists(self, _access_token):
            return [{"name": "Artist Two"}]

    client = BrokenLibraryClient(
        [
            track("one", "Stay", ["Artist One"]),
            track("two", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_uses_top_track_signal_only_to_order_existing_ambiguous_candidates():
    class TopSignalsClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return [track("top", "Stay", ["Artist Two"])]

        def get_top_artists(self, _access_token):
            return []

    client = TopSignalsClient(
        [
            track("other", "Stay", ["Artist One"]),
            track("top", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["top", "other"]


def test_catalog_uses_top_artist_signal_after_saved_and_top_track_signals():
    class TopSignalsClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return []

        def get_top_artists(self, _access_token):
            return [{"name": "Artist Two"}]

    client = TopSignalsClient(
        [
            track("other", "Stay", ["Artist One"]),
            track("top", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["top", "other"]


def test_catalog_applies_saved_then_top_then_recent_precedence_inside_existing_candidates():
    class PersonalizedClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [uri.endswith(":saved") for uri in track_uris]

        def get_top_tracks(self, _access_token):
            return [track("top", "Stay", ["Top Artist"])]

        def get_top_artists(self, _access_token):
            return []

        def get_recently_played(self, _access_token):
            return [
                {"track": track("recent", "Stay", ["Recent Artist"])},
                {"track": track("recent", "Stay", ["Recent Artist"])},
                {"track": track("other", "Other Song", ["Recent Artist"])},
            ]

    client = PersonalizedClient(
        [
            track("recent", "Stay", ["Recent Artist"]),
            track("top", "Stay", ["Top Artist"]),
            track("saved", "Stay", ["Saved Artist"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["saved", "top", "recent"]


def test_catalog_uses_recent_artist_signal_when_track_is_not_in_recent_history():
    class RecentClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return []

        def get_top_artists(self, _access_token):
            return []

        def get_recently_played(self, _access_token):
            return [{"track": track("history-track", "Other Song", ["Recent Artist"])}]

    client = RecentClient(
        [
            track("other", "Stay", ["Other Artist"]),
            track("recentartist", "Stay", ["Recent Artist"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["recentartist", "other"]


def test_catalog_recent_signal_cannot_create_a_new_candidate():
    class RecentOnlyClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return []

        def get_top_artists(self, _access_token):
            return []

        def get_recently_played(self, _access_token):
            return [{"track": track("not-in-search", "Stay", ["Unseen Artist"])}]

    client = RecentOnlyClient(
        [
            track("one", "Stay", ["Artist One"]),
            track("two", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_malformed_recent_history_falls_back_to_deterministic_order():
    class MalformedRecentClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return []

        def get_top_artists(self, _access_token):
            return []

        def get_recently_played(self, _access_token):
            return [{"track": {"id": "bad", "artists": [{"name": ""}]}}]

    client = MalformedRecentClient(
        [
            track("one", "Stay", ["Artist One"]),
            track("two", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


@pytest.mark.parametrize("status_code", [401, 403, 429])
def test_catalog_recent_history_api_failure_falls_back_safely(status_code):
    class FailedRecentClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return []

        def get_top_artists(self, _access_token):
            return []

        def get_recently_played(self, _access_token):
            from app.adapters.spotify.client import SpotifyApiError

            raise SpotifyApiError(status_code, "recent history unavailable")

    client = FailedRecentClient(
        [
            track("one", "Stay", ["Artist One"]),
            track("two", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_ignores_malformed_top_signals_and_keeps_deterministic_order():
    class MalformedTopSignalsClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return [{"name": "missing provider id"}]

        def get_top_artists(self, _access_token):
            return [{"id": "missing artist name"}]

    client = MalformedTopSignalsClient(
        [
            track("one", "Stay", ["Artist One"]),
            track("two", "Stay", ["Artist Two"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", None, access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["one", "two"]


def test_catalog_explicit_artist_relevance_precedes_top_signals():
    class TopSignalsClient(FakeSpotifySearchClient):
        def check_saved_tracks(self, _access_token, track_uris):
            return [False for _ in track_uris]

        def get_top_tracks(self, _access_token):
            return [track("weaker", "Stay", ["Artist Oner"])]

        def get_top_artists(self, _access_token):
            return [{"name": "Artist Oner"}]

        def get_recently_played(self, _access_token):
            return [{"track": track("weaker", "Stay", ["Artist Oner"])}]

    client = TopSignalsClient(
        [
            track("exact", "Stay", ["Artist One"]),
            track("weaker", "Stay", ["Artist Oner"]),
        ]
    )

    result = SpotifyCatalog(client).find_track("Stay", "Artist One", access_token="test-token")

    assert result.track is None
    assert result.ambiguous is True
    assert [candidate.track_id for candidate in result.candidates] == ["exact", "weaker"]


def test_catalog_ignores_out_of_range_popularity_metadata():
    ref = SpotifyCatalog._to_ref(track("trackone", "Stay", ["The Kid LAROI"], popularity=101))

    assert ref is not None
    assert ref.popularity is None


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


def test_catalog_marks_parser_split_reconstruction_failure_for_semantic_retry():
    catalog = SpotifyCatalog(FakeSpotifySearchClient([]))

    result = catalog.find_track(
        "終點",
        "死亡是生命",
        source_text="播放死亡是生命的終點",
        access_token="test-token",
    )

    assert result.track is None
    assert result.ambiguous is False
    assert result.retry_signal == "SPOTIFY_ENTITY_SEGMENTATION_RISK"


def test_catalog_keeps_ordinary_artist_track_miss_as_track_not_found():
    result = SpotifyCatalog(FakeSpotifySearchClient([])).find_track(
        "Missing Song",
        "Known Artist",
        source_text="play Missing Song by Known Artist",
        access_token="test-token",
    )

    assert result.track is None
    assert result.retry_signal is None


def test_catalog_marks_one_weak_candidate_as_low_confidence_for_semantic_retry():
    client = FakeSpotifySearchClient([track("weak", "Completely Different", ["Other Artist"])])

    result = SpotifyCatalog(client).find_track(
        "Requested Song",
        "Requested Artist",
        access_token="test-token",
    )

    assert result.track is None
    assert result.ambiguous is False
    assert result.candidates == ()
    assert result.retry_signal == "SPOTIFY_LOW_CONFIDENCE_TRACK"


def test_catalog_plays_a_strong_single_candidate_at_or_above_safe_threshold():
    client = FakeSpotifySearchClient([track("strong", "Requested Song", ["Requested Artist"])])

    result = SpotifyCatalog(client).find_track(
        "Requested Song",
        "Requested Artist",
        access_token="test-token",
    )

    assert result.track is not None
    assert result.retry_signal is None


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
