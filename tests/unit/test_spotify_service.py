import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest

from app.adapters.spotify.catalog import SpotifyCatalog, SpotifyTrackRef
from app.adapters.spotify.client import SpotifyApiClient, SpotifyApiError
from app.adapters.spotify.player import SpotifyPlayer
from app.adapters.windows.base import OperationResult
from app.domain.actions import ActionName, ValidatedAction
from app.infrastructure.spotify_auth import SpotifyAuthManager, SpotifyToken, SpotifyTokenStore
from app.services.spotify_clarification import ClarificationRecoveryRequest, SpotifyClarificationStore
from app.services.spotify_service import SpotifyService


def spotify_track(track_id, name, artist):
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "artists": [{"name": artist}],
        "album": {"name": "Album"},
    }


def trusted_track(track_id, name="Stay", artist="Artist"):
    return SpotifyTrackRef(
        track_id=track_id,
        track_uri=f"spotify:track:{track_id}",
        track_name=name,
        artist_names=(artist,),
        album_name="Album",
    )


class RecoveryAuth:
    def __init__(self):
        self.refresh_calls = 0

    def get_access_token(self):
        return "access-token"

    def refresh_access_token(self):
        self.refresh_calls += 1
        return "refreshed-token"


class RecoveryPlayer:
    def __init__(self):
        self.calls = []

    def resume(self, access_token, track=None):
        self.calls.append((access_token, track.track_id if track is not None else None))
        return OperationResult(True, "played", "OK", {"track_name": track.track_name} if track else {})


class RecoveryMemory:
    def __init__(self):
        self.calls = []

    def learn(self, event):
        self.calls.append(event)


def service(tmp_path, handler):
    client = SpotifyApiClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    store = SpotifyTokenStore(tmp_path / "spotify_token.json")
    store.save(
        SpotifyToken(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=10_000,
            scope="user-read-playback-state user-modify-playback-state",
        )
    )
    auth = SpotifyAuthManager(
        client_id="client-id",
        redirect_uri="http://127.0.0.1:8000/spotify/callback",
        token_store=store,
        client=client,
        clock=lambda: 1_000,
    )
    catalog = SpotifyCatalog(client)
    player = SpotifyPlayer(client, device_name="Windows Spotify", sleep=lambda _seconds: None, device_retries=0)
    return SpotifyService(auth, catalog, player), client


def test_named_track_service_searches_then_plays_the_server_selected_track(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
                return httpx.Response(200, json={"tracks": {"items": [spotify_track("stay1", "Stay", "The Kid LAROI")]}})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            assert request.url.params["device_id"] == "pc"
            assert json.loads(request.content) == {"uris": ["spotify:track:stay1"]}
            return httpx.Response(204)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(
        ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", artist="The Kid LAROI")
    )

    assert result.success is True
    assert result.data["track_name"] == "Stay"
    assert len(calls) == 3


def test_named_track_service_rejects_live_intent_without_search_or_playback(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(
        ValidatedAction(
            action=ActionName.SPOTIFY_PLAY_TRACK,
            track="晴天",
            artist="周杰倫",
            version_hint="live",
        )
    )

    assert result.success is False
    assert result.error_code == "SPOTIFY_LIVE_UNSUPPORTED"
    assert calls == []


def test_named_track_live_rejection_happens_before_authentication(tmp_path):
    class FailingAuth:
        def get_access_token(self):
            raise AssertionError("unsupported Live intent must not require Spotify auth")

    spotify = SpotifyService(FailingAuth(), object(), object())

    result = spotify.execute(
        ValidatedAction(
            action=ActionName.SPOTIFY_PLAY_TRACK,
            track="晴天",
            version_hint="live",
        )
    )

    assert result.success is False
    assert result.error_code == "SPOTIFY_LIVE_UNSUPPORTED"


def test_parser_split_reconstruction_failure_exposes_entity_retry_signal(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        assert request.url.path == "/v1/search"
        return httpx.Response(200, json={"tracks": {"items": []}})

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(
        ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="終點", artist="死亡是生命"),
        source_text="播放死亡是生命的終點",
    )

    assert result.success is False
    assert result.error_code == "SPOTIFY_ENTITY_SEGMENTATION_RISK"
    # The failed deterministic lookup now makes one bounded title-first
    # recovery attempt before preserving the parser retry signal.
    assert len(calls) == 3


def test_single_weak_candidate_exposes_low_confidence_retry_signal(tmp_path):
    def handler(request: httpx.Request):
        assert request.url.path == "/v1/search"
        return httpx.Response(
            200,
            json={"tracks": {"items": [spotify_track("weak", "Completely Different", "Other Artist")]}},
        )

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(
        ValidatedAction(
            action=ActionName.SPOTIFY_PLAY_TRACK,
            track="Requested Song",
            artist="Requested Artist",
        )
    )

    assert result.success is False
    assert result.error_code == "SPOTIFY_LOW_CONFIDENCE_TRACK"


def test_ambiguous_search_never_reaches_playback_endpoint(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        assert request.url.path == "/v1/search"
        return httpx.Response(
            200,
            json={"tracks": {"items": [spotify_track("one", "Stay", "The Kid LAROI"), spotify_track("two", "Stay", "The Kid LAROI")]}},
        )

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", artist="The Kid LAROI"))

    assert result.success is False
    assert result.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    assert result.data["clarification_required"] is True
    assert result.data["clarification_token"]
    assert [request.url.path for request in calls] == [
        "/v1/search",
        "/v1/me/library/contains",
        "/v1/me/top/tracks",
        "/v1/me/top/artists",
        "/v1/me/player/recently-played",
    ]


def test_ambiguous_search_issues_at_most_three_trusted_options(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False, False])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        assert request.url.path == "/v1/search"
        return httpx.Response(
            200,
            json={
                "tracks": {
                    "items": [
                        spotify_track(str(index), "Stay", "The Kid LAROI")
                        for index in range(4)
                    ]
                }
            },
        )

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", artist="The Kid LAROI"))

    assert result.success is False
    assert result.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    assert result.data["clarification_required"] is True
    assert result.data["clarification_type"] == "spotify_track"
    assert len(result.data["options"]) == 3
    assert result.data["clarification_token"]
    assert [request.url.path for request in calls] == [
        "/v1/search",
        "/v1/me/library/contains",
        "/v1/me/top/tracks",
        "/v1/me/top/artists",
        "/v1/me/player/recently-played",
    ]


def test_none_of_these_recovers_a_server_owned_page_without_auto_play(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            assert request.url.params["q"] == "track:Stay"
            if request.url.params["offset"] == "0":
                items = [
                    spotify_track("wrongone", "Stay", "Artist One"),
                    spotify_track("wrongtwo", "Stay", "Artist Two"),
                    spotify_track("wrongthree", "Stay", "Artist Three"),
                ]
            else:
                assert request.url.params["offset"] == "10"
                items = [
                    spotify_track("wrongone", "Stay", "Artist One"),
                    spotify_track("desired", "Stay", "The Kid LAROI"),
                ]
            return httpx.Response(200, json={"tracks": {"items": items}})
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False] * len(request.url.params["uris"].split(",")))
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            assert json.loads(request.content) == {"uris": ["spotify:track:desired"]}
            return httpx.Response(204)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))

    assert initial.success is False
    assert initial.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    token = initial.data["clarification_token"]
    assert "desired" not in repr(initial.data)
    assert not any(request.url.path == "/v1/me/player/play" for request in calls)

    recovered = spotify.execute_clarification("都不是", token)

    assert recovered.success is False
    assert recovered.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    recovered_token = recovered.data["clarification_token"]
    assert recovered_token != token
    assert [option["artist_names"][0] for option in recovered.data["options"]] == ["The Kid LAROI"]
    assert not any(request.url.path == "/v1/me/player/play" for request in calls)

    selected = spotify.execute_clarification("第一首", recovered_token)

    assert selected.success is True
    assert selected.data["track_name"] == "Stay"
    assert len([request for request in calls if request.url.path == "/v1/me/player/play"]) == 1


def test_none_of_these_exhaustion_excludes_duplicates_and_live_tracks(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            assert request.url.params["q"] == "track:Stay"
            if request.url.params["offset"] == "0":
                items = [
                    spotify_track("one", "Stay", "Artist One"),
                    spotify_track("two", "Stay", "Artist Two"),
                    spotify_track("three", "Stay", "Artist Three"),
                ]
            else:
                items = [
                    spotify_track("one", "Stay", "Artist One"),
                    spotify_track("live", "Stay (Live)", "Artist Four"),
                ]
            return httpx.Response(200, json={"tracks": {"items": items}})
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False] * len(request.url.params["uris"].split(",")))
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))
    exhausted = spotify.execute_clarification("none of these", initial.data["clarification_token"])

    assert exhausted.success is False
    assert exhausted.error_code == "SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED"
    assert exhausted.data["clarification_token"] == initial.data["clarification_token"]
    assert not any(request.url.path == "/v1/me/player/play" for request in calls)


def recovery_service(catalog, memory=None):
    auth = RecoveryAuth()
    player = RecoveryPlayer()
    store = SpotifyClarificationStore()
    token = store.create(
        [trusted_track("one")],
        recovery_request=ClarificationRecoveryRequest(track="Stay"),
    )
    service = SpotifyService(
        auth,
        catalog,
        player,
        clarification_store=store,
        memory_learner=memory,
    )
    return service, auth, player, store, token


def test_provider_recovery_concurrency_fetches_once_and_rotates_token():
    class BlockingCatalog:
        def __init__(self):
            self.calls = []
            self.started = Event()
            self.release = Event()

        def recover_candidates(self, track, artist, album, **kwargs):
            self.calls.append(kwargs["access_token"])
            self.started.set()
            assert self.release.wait(5)
            return (trusted_track("two"),)

    catalog = BlockingCatalog()
    service, _auth, _player, store, token = recovery_service(catalog)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(service.execute_clarification, "none of these", token)
        assert catalog.started.wait(5)
        second_future = executor.submit(service.execute_clarification, "none of these", token)
        second = second_future.result(timeout=5)
        blocked_selection = service.execute_clarification("第一首", token)
        catalog.release.set()
        first = first_future.result(timeout=5)

    assert len(catalog.calls) == 1
    assert first.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    next_token = first.data["clarification_token"]
    assert next_token != token
    assert second.error_code == "SPOTIFY_CLARIFICATION_RECOVERY_IN_PROGRESS"
    assert blocked_selection.error_code == "SPOTIFY_CLARIFICATION_RECOVERY_IN_PROGRESS"
    assert store.select(token, "第一首").error_code == "SPOTIFY_CLARIFICATION_USED"
    assert store.select(next_token, "第一首").track.track_id == "two"


def test_provider_recovery_401_refreshes_once_and_completes_one_transition():
    class RefreshingCatalog:
        def __init__(self):
            self.calls = []

        def recover_candidates(self, track, artist, album, **kwargs):
            self.calls.append(kwargs["access_token"])
            if len(self.calls) == 1:
                raise SpotifyApiError(401, "unauthorized")
            return (trusted_track("two"),)

    catalog = RefreshingCatalog()
    memory = RecoveryMemory()
    service, auth, player, store, token = recovery_service(catalog, memory)

    result = service.execute_clarification("none of these", token)

    assert result.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    next_token = result.data["clarification_token"]
    assert next_token != token
    assert catalog.calls == ["access-token", "refreshed-token"]
    assert auth.refresh_calls == 1
    assert player.calls == []
    assert memory.calls == []
    assert store.select(token, "第一首").error_code == "SPOTIFY_CLARIFICATION_USED"
    assert store.select(next_token, "第一首").track.track_id == "two"


@pytest.mark.parametrize(
    ("status_code", "retry_after_seconds", "expected_code"),
    [
        (403, None, "SPOTIFY_FORBIDDEN"),
        (429, 17, "SPOTIFY_RATE_LIMITED"),
    ],
)
def test_provider_recovery_errors_fail_closed_without_retry_or_memory(
    status_code, retry_after_seconds, expected_code
):
    class FailingCatalog:
        def __init__(self):
            self.calls = 0

        def recover_candidates(self, track, artist, album, **kwargs):
            self.calls += 1
            raise SpotifyApiError(
                status_code,
                "provider failure",
                retry_after_seconds=retry_after_seconds,
                reason="QUOTA_EXCEEDED" if status_code == 429 else None,
            )

    catalog = FailingCatalog()
    memory = RecoveryMemory()
    service, auth, player, store, token = recovery_service(catalog, memory)

    result = service.execute_clarification("none of these", token)

    assert result.success is False
    assert result.error_code == expected_code
    assert catalog.calls == 1
    assert auth.refresh_calls == 0
    assert player.calls == []
    assert memory.calls == []
    if status_code == 429:
        assert result.data == {"retry_after_seconds": 17}
    else:
        assert result.data == {}
    assert store.select(token, "第一首").track.track_id == "one"


def test_ambiguous_search_uses_saved_status_to_order_options_without_auto_playing(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("other", "Stay", "Artist One"),
                            spotify_track("saved", "Stay", "Artist Two"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            assert request.url.params["uris"] == "spotify:track:other,spotify:track:saved"
            return httpx.Response(200, json=[False, True])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))

    assert result.success is False
    assert result.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    assert [option["artist_names"][0] for option in result.data["options"]] == ["Artist Two", "Artist One"]
    assert [request.url.path for request in calls] == [
        "/v1/search",
        "/v1/me/library/contains",
        "/v1/me/top/tracks",
        "/v1/me/top/artists",
        "/v1/me/player/recently-played",
    ]


def test_clarification_selection_plays_only_the_server_stored_candidate(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("one", "Stay", "Artist One"),
                            spotify_track("two", "Stay", "Artist Two"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            assert json.loads(request.content) == {"uris": ["spotify:track:two"]}
            return httpx.Response(204)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))
    token = initial.data["clarification_token"]

    selected = spotify.execute_clarification("第二首", token)

    assert selected.success is True
    assert selected.data["track_name"] == "Stay"
    assert [request.url.path for request in calls] == [
        "/v1/search",
        "/v1/me/library/contains",
        "/v1/me/top/tracks",
        "/v1/me/top/artists",
        "/v1/me/player/recently-played",
        "/v1/me/player/devices",
        "/v1/me/player/play",
    ]


def test_ordinary_personalization_429_does_not_block_clarification_playback(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("one", "Stay", "Artist One"),
                            spotify_track("two", "Stay", "Artist Two"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        if request.url.path == "/v1/me/top/tracks":
            return httpx.Response(
                429,
                headers={"Retry-After": "30"},
                json={"error": {"reason": "RATE_LIMITED"}},
            )
        if request.url.path in {"/v1/me/top/artists", "/v1/me/player/recently-played"}:
            raise AssertionError(f"scoped personalization cooldown should suppress {request.url.path}")
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            assert json.loads(request.content) == {"uris": ["spotify:track:two"]}
            return httpx.Response(204)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))

    assert initial.success is False
    assert initial.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    token = initial.data["clarification_token"]

    selected = spotify.execute_clarification("第二首", token)

    assert selected.success is True
    assert [request.url.path for request in calls] == [
        "/v1/search",
        "/v1/me/library/contains",
        "/v1/me/top/tracks",
        "/v1/me/player/devices",
        "/v1/me/player/play",
    ]


def test_unclear_clarification_keeps_the_same_bounded_context(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("one", "Stay", "Artist One"),
                            spotify_track("two", "Stay", "Artist Two"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))
    token = initial.data["clarification_token"]

    unclear = spotify.execute_clarification("那一首", token)

    assert unclear.success is False
    assert unclear.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert unclear.data["clarification_token"] == token
    assert len(unclear.data["options"]) == 2
    assert [request.url.path for request in calls] == [
        "/v1/search",
        "/v1/me/library/contains",
        "/v1/me/top/tracks",
        "/v1/me/top/artists",
        "/v1/me/player/recently-played",
    ]


def test_unclear_clarification_expires_after_bounded_attempts(tmp_path):
    def handler(request: httpx.Request):
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("one", "Stay", "Artist One"),
                            spotify_track("two", "Stay", "Artist Two"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))
    token = initial.data["clarification_token"]

    first = spotify.execute_clarification("不知道", token)
    second = spotify.execute_clarification("還是不知道", token)
    exhausted = spotify.execute_clarification("隨便", token)

    assert first.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert second.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert exhausted.error_code == "SPOTIFY_CLARIFICATION_ATTEMPTS_EXHAUSTED"
    assert exhausted.message == "歌曲選擇嘗試次數已用完，請重新說出歌曲。"
    assert "clarification_token" not in exhausted.data


def test_401_refreshes_once_then_retries_the_fixed_operation(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/v1/me/player/devices" and len([call for call in calls if call[0] == request.url.path]) == 1:
            return httpx.Response(401, json={"error": {"status": 401}})
        if request.url.host == "accounts.spotify.com" and request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "refreshed-access", "expires_in": 3600})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/pause":
            return httpx.Response(204)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PAUSE))

    assert result.success is True
    device_headers = [auth for path, auth in calls if path == "/v1/me/player/devices"]
    assert device_headers == ["Bearer access-token", "Bearer refreshed-access"]


@pytest.mark.parametrize(
    ("reason", "expected_provider_reason"),
    [
        ("PREMIUM_REQUIRED", "PREMIUM_REQUIRED"),
        (None, None),
        ("Premium required", None),
        ("x" * 65, None),
    ],
)
def test_forbidden_provider_reason_is_bounded_and_non_sensitive(tmp_path, reason, expected_provider_reason):
    payload = {
        "error": {
            "status": 403,
            "message": "raw-provider-secret access-token=secret-token",
        },
        "track_id": "private-track-id",
        "uri": "spotify:track:private-uri",
    }
    if reason is not None:
        payload["error"]["reason"] = reason

    def forbidden_handler(request: httpx.Request):
        return httpx.Response(403, json=payload)

    forbidden, _ = service(tmp_path / f"forbidden-{expected_provider_reason or 'none'}", forbidden_handler)
    forbidden_result = forbidden.execute(ValidatedAction(action=ActionName.SPOTIFY_PAUSE))

    assert forbidden_result.success is False
    assert forbidden_result.error_code == "SPOTIFY_FORBIDDEN"
    assert forbidden_result.message == "Spotify 拒絕這項播放操作，請確認 Premium 與帳戶狀態。"
    expected_data = {"provider_reason": expected_provider_reason} if expected_provider_reason else {}
    assert forbidden_result.data == expected_data
    rendered = repr(forbidden_result)
    assert "raw-provider-secret" not in rendered
    assert "secret-token" not in rendered
    assert "private-track-id" not in rendered
    assert "spotify:track:private-uri" not in rendered

    def limited_handler(request: httpx.Request):
        return httpx.Response(
            429,
            headers={"Retry-After": "9"},
            json={"error": {"status": 429, "reason": "RATE_LIMITED"}},
        )

    limited, _ = service(tmp_path / "limited", limited_handler)
    limited_result = limited.execute(ValidatedAction(action=ActionName.SPOTIFY_PAUSE))
    assert limited_result.success is False
    assert limited_result.error_code == "SPOTIFY_RATE_LIMITED"
    assert limited_result.message == "Spotify 目前請求過多，請稍後再試。"
    assert limited_result.data == {"retry_after_seconds": 9}


def test_state_control_actions_dispatch_to_fixed_player_operations(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/shuffle":
            assert request.method == "PUT"
            assert request.url.params["state"] == "true"
            assert request.url.params["device_id"] == "pc"
            assert request.content == b""
            return httpx.Response(204)
        if request.url.path == "/v1/me/player/repeat":
            assert request.method == "PUT"
            assert request.url.params["device_id"] == "pc"
            assert request.content == b""
            return httpx.Response(204)
        if request.url.path == "/v1/me/player/play":
            assert request.method == "PUT"
            assert request.url.params["device_id"] == "pc"
            assert request.content == b""
            return httpx.Response(204)
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)

    shuffle = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_SHUFFLE_ON))
    repeat = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_REPEAT_CONTEXT))
    continued = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_CONTINUE))

    assert shuffle.success is True
    assert repeat.success is True
    assert continued.success is True
    assert [request.url.path for request in calls] == [
        "/v1/me/player/devices",
        "/v1/me/player/shuffle",
        "/v1/me/player/devices",
        "/v1/me/player/repeat",
        "/v1/me/player/devices",
        "/v1/me/player/repeat",
        "/v1/me/player/play",
    ]


def test_continue_surfaces_repeat_failure_and_does_not_resume_partially(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/repeat":
            return httpx.Response(429, headers={"Retry-After": "6"}, json={"error": {"reason": "RATE_LIMITED"}})
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_CONTINUE))

    assert result.success is False
    assert result.error_code == "SPOTIFY_RATE_LIMITED"
    assert result.data == {"retry_after_seconds": 6}
    assert calls == ["/v1/me/player/devices", "/v1/me/player/repeat"]
