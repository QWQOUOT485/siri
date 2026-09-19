import httpx
import pytest

from app.adapters.spotify.client import SpotifyApiClient, SpotifyApiError


def client_for(handler):
    transport = httpx.MockTransport(handler)
    return SpotifyApiClient(http_client=httpx.Client(transport=transport))


def test_search_uses_only_the_fixed_spotify_search_endpoint():
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/v1/search"
        assert request.url.params["q"] == "track:Stay artist:The Kid LAROI"
        assert request.url.params["type"] == "track"
        assert request.url.params["limit"] == "10"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json={"tracks": {"items": [{"id": "track-1"}]}})

    client = client_for(handler)

    assert client.search_tracks("access-token", "track:Stay artist:The Kid LAROI") == [{"id": "track-1"}]


def test_saved_track_lookup_uses_only_server_owned_track_uris_and_preserves_order():
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/v1/me/library/contains"
        assert request.url.params["uris"] == "spotify:track:one,spotify:track:two"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json=[True, False])

    client = client_for(handler)

    assert client.check_saved_tracks("access-token", ("spotify:track:one", "spotify:track:two")) == [True, False]


def test_saved_track_lookup_rejects_arbitrary_uris_and_unbounded_batches():
    client = client_for(lambda _request: httpx.Response(200, json=[False]))

    with pytest.raises(ValueError):
        client.check_saved_tracks("access-token", ("https://evil.example/track",))
    with pytest.raises(ValueError):
        client.check_saved_tracks("access-token", tuple(f"spotify:track:{index}" for index in range(4)))


def test_top_track_and_artist_lookups_use_fixed_endpoints_and_bounded_limit():
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.params["limit"] == "50"
        if request.url.path == "/v1/me/top/tracks":
            return httpx.Response(200, json={"items": [{"id": "top-track"}]})
        if request.url.path == "/v1/me/top/artists":
            return httpx.Response(200, json={"items": [{"name": "Top Artist"}]})
        raise AssertionError(request.url)

    client = client_for(handler)

    assert client.get_top_tracks("access-token", limit=999) == [{"id": "top-track"}]
    assert client.get_top_artists("access-token", limit=999) == [{"name": "Top Artist"}]


def test_top_lookup_rejects_malformed_items_without_exposing_generic_http():
    client = client_for(lambda _request: httpx.Response(200, json={"items": "not-a-list"}))

    with pytest.raises(SpotifyApiError) as error:
        client.get_top_tracks("access-token")

    assert error.value.status_code == 200


def test_recently_played_lookup_uses_fixed_endpoint_and_bounded_limit():
    recent_item = {
        "played_at": "2026-09-20T00:00:00.000Z",
        "track": {
            "id": "recent-track",
            "name": "Stay",
            "artists": [{"name": "Recent Artist"}],
        },
    }

    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/v1/me/player/recently-played"
        assert request.url.params["limit"] == "50"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json={"items": [recent_item]})

    client = client_for(handler)

    assert client.get_recently_played("access-token", limit=999) == [recent_item]


def test_recently_played_lookup_rejects_malformed_items_without_generic_fallback():
    client = client_for(lambda _request: httpx.Response(200, json={"items": [{"track": "not-a-track"}]}))

    with pytest.raises(SpotifyApiError) as error:
        client.get_recently_played("access-token")

    assert error.value.status_code == 200


def test_pkce_code_exchange_uses_form_data_and_does_not_use_a_client_secret():
    def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.host == "accounts.spotify.com"
        assert request.url.path == "/api/token"
        body = dict(item.split("=", 1) for item in request.content.decode().split("&"))
        assert body["grant_type"] == "authorization_code"
        assert body["client_id"] == "client-id"
        assert body["code"] == "auth-code"
        assert body["code_verifier"] == "verifier"
        assert "client_secret" not in body
        return httpx.Response(200, json={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})

    client = client_for(handler)

    result = client.exchange_code("client-id", "auth-code", "http://127.0.0.1:8000/spotify/callback", "verifier")

    assert result["access_token"] == "access"


def test_rate_limit_error_preserves_retry_after_without_leaking_the_access_token():
    def handler(_request: httpx.Request):
        return httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "rate limited"})

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as error:
        client.get_devices("super-secret-access-token")

    assert error.value.status_code == 429
    assert error.value.retry_after_seconds == 7
    assert "super-secret-access-token" not in str(error.value)


def test_playback_controls_accept_successful_non_json_responses():
    def handler(request: httpx.Request):
        assert request.url.path in {"/v1/me/player/pause", "/v1/me/player/next"}
        return httpx.Response(200, content=b"Playback command accepted")

    client = client_for(handler)

    client.pause("access-token")
    client.next("access-token")


def test_current_playback_uses_the_fixed_player_state_endpoint():
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/v1/me/player"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json={"item": {"id": "track-1"}, "is_playing": True})

    client = client_for(handler)

    assert client.get_current_playback("access-token") == {"item": {"id": "track-1"}, "is_playing": True}
