from concurrent.futures import ThreadPoolExecutor

import pytest

from app.adapters.spotify.catalog import SpotifyTrackRef
from app.services.spotify_clarification import ClarificationRecoveryRequest, SpotifyClarificationStore


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


def test_store_pages_server_owned_recovery_candidates_without_client_cursor():
    first_page = [
        candidate("one", "Artist One", "Album One"),
        candidate("two", "Artist Two", "Album Two"),
        candidate("three", "Artist Three", "Album Three"),
    ]
    second_page = [
        candidate("four", "Artist Four", "Album Four"),
        candidate("five", "Artist Five", "Album Five"),
    ]
    store = SpotifyClarificationStore()
    token = store.create(
        first_page,
        recovery_candidates=[*first_page, *second_page],
        recovery_request=ClarificationRecoveryRequest(track="Stay"),
    )

    next_page = store.select(token, "都不是")

    assert next_page.error_code == "SPOTIFY_CLARIFICATION_NEXT_PAGE"
    assert [track.track_id for track in next_page.candidates] == ["four", "five"]
    assert next_page.clarification_token
    assert next_page.clarification_token != token
    assert store.select(token, "第一首").error_code == "SPOTIFY_CLARIFICATION_USED"
    assert store.select(next_page.clarification_token, "第一首").track.track_id == "four"


def test_store_requests_bounded_server_recovery_when_local_pool_is_exhausted():
    first_page = [candidate("one", "Artist One", "Album One")]
    fetched = [candidate("two", "Artist Two", "Album Two")]
    store = SpotifyClarificationStore(max_recovery_rounds=1)
    token = store.create(
        first_page,
        recovery_request=ClarificationRecoveryRequest(track="Stay"),
    )

    request = store.select(token, "none of these")

    assert request.error_code == "SPOTIFY_CLARIFICATION_RECOVERY_REQUESTED"
    assert request.recovery_request is not None
    assert request.recovery_fetch_index == 1
    assert request.shown_track_ids == ("one",)

    page = store.complete_recovery(token, request.recovery_fetch_index, fetched)

    assert page.error_code == "SPOTIFY_CLARIFICATION_NEXT_PAGE"
    assert [track.track_id for track in page.candidates] == ["two"]
    assert page.clarification_token
    assert page.clarification_token != token
    assert store.select(token, "都不是").error_code == "SPOTIFY_CLARIFICATION_USED"
    exhausted = store.select(page.clarification_token, "都不是")
    assert exhausted.error_code == "SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED"
    assert exhausted.clarification_token == page.clarification_token


def test_store_concurrent_local_recovery_rotates_once_and_consumes_old_token():
    first_page = [candidate(str(index), f"Artist {index}", f"Album {index}") for index in range(1, 4)]
    recovery_pool = [candidate(str(index), f"Artist {index}", f"Album {index}") for index in range(4, 10)]
    store = SpotifyClarificationStore()
    token = store.create(first_page, recovery_candidates=recovery_pool)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: store.select(token, "都不是"), range(2)))

    pages = [result for result in results if result.error_code == "SPOTIFY_CLARIFICATION_NEXT_PAGE"]
    used = [result for result in results if result.error_code == "SPOTIFY_CLARIFICATION_USED"]

    assert len(pages) == 1
    assert len(used) == 1
    next_page = pages[0]
    assert next_page.clarification_token
    assert next_page.clarification_token != token
    assert [track.track_id for track in next_page.candidates] == ["4", "5", "6"]
    assert store.select(token, "第一首").error_code == "SPOTIFY_CLARIFICATION_USED"
    assert store.select(next_page.clarification_token, "第一首").track.track_id == "4"


def test_store_recovery_round_limit_applies_to_local_pages():
    first_page = [candidate(str(index), f"Artist {index}", f"Album {index}") for index in range(1, 4)]
    recovery_pool = [candidate(str(index), f"Artist {index}", f"Album {index}") for index in range(4, 11)]
    store = SpotifyClarificationStore(max_recovery_rounds=2)
    token = store.create(
        first_page,
        recovery_candidates=recovery_pool,
        recovery_request=ClarificationRecoveryRequest(track="Stay"),
    )

    page_one = store.select(token, "換一批")
    page_two = store.select(page_one.clarification_token, "換一批")
    exhausted = store.select(page_two.clarification_token, "換一批")

    assert [track.track_id for track in page_one.candidates] == ["4", "5", "6"]
    assert [track.track_id for track in page_two.candidates] == ["7", "8", "9"]
    assert page_one.clarification_token not in {token, page_two.clarification_token}
    assert exhausted.error_code == "SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED"
    assert exhausted.clarification_token == page_two.clarification_token


@pytest.mark.parametrize(
    "phrase",
    ["都不是", "不是這些", "換一批", "再一批", "none of these", "not these", "another batch", "next batch", "different ones"],
)
def test_store_accepts_only_reviewed_exact_recovery_phrases(phrase):
    store = SpotifyClarificationStore()
    token = store.create(
        [candidate("one", "Artist One", "Album One")],
        recovery_candidates=[candidate("two", "Artist Two", "Album Two")],
    )

    result = store.select(token, phrase)

    assert result.error_code == "SPOTIFY_CLARIFICATION_NEXT_PAGE"


@pytest.mark.parametrize("phrase", ["都不是第一首", "none of these please play first", "another batch please"])
def test_store_rejects_unreviewed_recovery_phrase_prefixes(phrase):
    store = SpotifyClarificationStore()
    token = store.create(
        [candidate("one", "Artist One", "Album One")],
        recovery_candidates=[candidate("two", "Artist Two", "Album Two")],
    )

    result = store.select(token, phrase)

    assert result.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
