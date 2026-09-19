import json

import httpx

from app.adapters.spotify.catalog import SpotifyCatalog
from app.adapters.spotify.client import SpotifyApiClient
from app.adapters.spotify.player import SpotifyPlayer
from app.domain.actions import ActionName, ValidatedAction
from app.infrastructure.spotify_auth import SpotifyAuthManager, SpotifyToken, SpotifyTokenStore
from app.services.spotify_service import SpotifyService


def spotify_track(track_id, name, artist):
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "artists": [{"name": artist}],
        "album": {"name": "Album"},
    }


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
    assert len(calls) == 2


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
    assert [request.url.path for request in calls] == ["/v1/search", "/v1/me/library/contains"]


def test_ambiguous_search_issues_at_most_three_trusted_options(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False, False])
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
    assert [request.url.path for request in calls] == ["/v1/search", "/v1/me/library/contains"]


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
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))

    assert result.success is False
    assert result.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    assert [option["artist_names"][0] for option in result.data["options"]] == ["Artist Two", "Artist One"]
    assert [request.url.path for request in calls] == ["/v1/search", "/v1/me/library/contains"]


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
    assert [request.url.path for request in calls] == ["/v1/search", "/v1/me/library/contains", "/v1/me/player/devices", "/v1/me/player/play"]


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
        raise AssertionError(request.url)

    spotify, _ = service(tmp_path, handler)
    initial = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay"))
    token = initial.data["clarification_token"]

    unclear = spotify.execute_clarification("那一首", token)

    assert unclear.success is False
    assert unclear.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert unclear.data["clarification_token"] == token
    assert len(unclear.data["options"]) == 2
    assert [request.url.path for request in calls] == ["/v1/search", "/v1/me/library/contains"]


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


def test_forbidden_and_rate_limited_responses_are_safe_and_bounded(tmp_path):
    def forbidden_handler(request: httpx.Request):
        return httpx.Response(403, json={"error": {"status": 403}})

    forbidden, _ = service(tmp_path / "forbidden", forbidden_handler)
    forbidden_result = forbidden.execute(ValidatedAction(action=ActionName.SPOTIFY_PAUSE))
    assert forbidden_result.error_code == "SPOTIFY_FORBIDDEN"

    def limited_handler(request: httpx.Request):
        return httpx.Response(429, headers={"Retry-After": "9"}, json={"error": {"status": 429}})

    limited, _ = service(tmp_path / "limited", limited_handler)
    limited_result = limited.execute(ValidatedAction(action=ActionName.SPOTIFY_PAUSE))
    assert limited_result.error_code == "SPOTIFY_RATE_LIMITED"
    assert limited_result.data == {"retry_after_seconds": 9}
