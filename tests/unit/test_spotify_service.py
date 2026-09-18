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


def test_named_track_service_passes_live_intent_to_catalog_and_playback(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/search":
            assert request.url.params["q"] == "track:晴天 artist:周杰倫 live"
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("studio", "晴天", "周杰倫"),
                            {**spotify_track("live", "晴天", "周杰倫"), "album": {"name": "2004 Live"}},
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            assert json.loads(request.content) == {"uris": ["spotify:track:live"]}
            return httpx.Response(204)
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

    assert result.success is True
    assert result.data["track_name"] == "晴天"
    assert result.data["album_name"] == "2004 Live"


def test_ambiguous_search_never_reaches_playback_endpoint(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        assert request.url.path == "/v1/search"
        return httpx.Response(
            200,
            json={"tracks": {"items": [spotify_track("one", "Stay", "The Kid LAROI"), spotify_track("two", "Stay", "The Kid LAROI")]}},
        )

    spotify, _ = service(tmp_path, handler)

    result = spotify.execute(ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", artist="The Kid LAROI"))

    assert result.success is False
    assert result.error_code == "SPOTIFY_AMBIGUOUS_TRACK"
    assert len(calls) == 1


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
