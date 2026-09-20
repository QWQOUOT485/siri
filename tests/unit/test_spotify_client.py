import httpx
import pytest

from app.adapters.spotify.client import SpotifyApiClient, SpotifyApiError


def client_for(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    return SpotifyApiClient(http_client=httpx.Client(transport=transport), **kwargs)


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


def test_search_recovery_offset_is_server_bounded():
    def handler(request: httpx.Request):
        assert request.url.params["offset"] == "50"
        assert request.url.params["limit"] == "10"
        return httpx.Response(200, json={"tracks": {"items": []}})

    client = client_for(handler)

    assert client.search_tracks("access-token", "track:Stay", offset=999) == []


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
        return httpx.Response(
            429,
            headers={"Retry-After": "7"},
            json={"error": {"status": 429, "message": "Too many requests", "reason": "QUOTA_EXCEEDED"}},
        )

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as error:
        client.get_devices("super-secret-access-token")

    assert error.value.status_code == 429
    assert error.value.retry_after_seconds == 7
    assert error.value.reason == "QUOTA_EXCEEDED"
    assert "super-secret-access-token" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        {"error": {"reason": "x" * 65}},
        {"error": {"reason": "quota exceeded"}},
        {"error": "rate limited"},
        {"message": "rate limited"},
    ],
)
def test_rate_limit_reason_rejects_unbounded_or_malformed_provider_payloads(payload):
    client = client_for(lambda _request: httpx.Response(429, json=payload))

    with pytest.raises(SpotifyApiError) as error:
        client.get_devices("access-token")

    assert error.value.reason is None


def test_rate_limit_cooldown_fails_fast_without_a_second_transport_call():
    class FakeClock:
        now = 100.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            429,
            headers={"Retry-After": "30"},
            json={"error": {"reason": "QUOTA_EXCEEDED"}},
        )

    client = client_for(handler, clock=clock)

    with pytest.raises(SpotifyApiError):
        client.get_devices("access-token")
    with pytest.raises(SpotifyApiError) as second_error:
        client.get_devices("access-token")

    assert calls == 1
    assert second_error.value.status_code == 429
    assert second_error.value.retry_after_seconds == 30
    assert second_error.value.reason == "QUOTA_EXCEEDED"

    clock.now += 30
    with pytest.raises(SpotifyApiError):
        client.get_devices("access-token")
    assert calls == 2


def test_explicit_quota_exhaustion_from_personalization_blocks_playback_web_api():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/v1/me/top/tracks":
            return httpx.Response(
                429,
                headers={"Retry-After": "30"},
                json={"error": {"reason": "QUOTA_EXCEEDED"}},
            )
        raise AssertionError(request.url)

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as first_error:
        client.get_top_tracks("access-token")
    with pytest.raises(SpotifyApiError) as playback_error:
        client.get_devices("access-token")

    assert first_error.value.reason == "QUOTA_EXCEEDED"
    assert playback_error.value.reason == "QUOTA_EXCEEDED"
    assert playback_error.value.retry_after_seconds == 30
    assert calls == ["/v1/me/top/tracks"]


def test_ordinary_personalization_429_does_not_block_playback_scope():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/v1/me/top/tracks":
            return httpx.Response(
                429,
                headers={"Retry-After": "30"},
                json={"error": {"reason": "RATE_LIMITED"}},
            )
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": []})
        if request.url.path == "/v1/me/player/play":
            return httpx.Response(204)
        raise AssertionError(request.url)

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as personalization_error:
        client.get_top_tracks("access-token")
    assert personalization_error.value.reason == "RATE_LIMITED"
    assert client.get_devices("access-token") == []
    client.start_resume("access-token")

    assert calls == [
        "/v1/me/top/tracks",
        "/v1/me/player/devices",
        "/v1/me/player/play",
    ]


def test_ordinary_search_429_does_not_block_playback_scope():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/v1/search":
            return httpx.Response(429, json={"error": {"reason": "RATE_LIMITED"}})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": []})
        raise AssertionError(request.url)

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as search_error:
        client.search_tracks("access-token", "track:Stay")
    assert search_error.value.reason == "RATE_LIMITED"
    assert client.get_devices("access-token") == []
    assert calls == ["/v1/search", "/v1/me/player/devices"]


def test_ordinary_playback_429_does_not_poison_personalization_scope():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/v1/me/player/pause":
            return httpx.Response(429, json={"error": {"reason": "RATE_LIMITED"}})
        if request.url.path == "/v1/me/top/tracks":
            return httpx.Response(200, json={"items": [{"id": "top-track"}]})
        raise AssertionError(request.url)

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as playback_error:
        client.pause("access-token")
    assert playback_error.value.reason == "RATE_LIMITED"
    assert client.get_top_tracks("access-token") == [{"id": "top-track"}]
    assert calls == ["/v1/me/player/pause", "/v1/me/top/tracks"]


def test_ordinary_personalization_cooldown_expires_with_fake_clock():
    class FakeClock:
        now = 100.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "30"}, json={"error": {"reason": "RATE_LIMITED"}})
        return httpx.Response(200, json={"items": [{"id": "top-track"}]})

    client = client_for(handler, clock=clock)

    with pytest.raises(SpotifyApiError):
        client.get_top_tracks("access-token")
    with pytest.raises(SpotifyApiError) as cooldown_error:
        client.get_top_tracks("access-token")
    assert cooldown_error.value.reason == "RATE_LIMITED"
    assert calls == 1

    clock.now += 30
    assert client.get_top_tracks("access-token") == [{"id": "top-track"}]
    assert calls == 2


def test_malformed_retry_after_uses_a_short_local_cooldown_without_sleeping():
    class FakeClock:
        now = 10.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "not-a-number"}, json={"error": {}})
        return httpx.Response(200, json={"devices": []})

    client = client_for(handler, clock=clock, default_rate_limit_cooldown_seconds=5)

    with pytest.raises(SpotifyApiError) as first_error:
        client.get_devices("access-token")
    assert first_error.value.retry_after_seconds is None

    with pytest.raises(SpotifyApiError) as second_error:
        client.get_devices("access-token")
    assert second_error.value.retry_after_seconds == 5
    assert calls == 1

    clock.now += 5
    assert client.get_devices("access-token") == []
    assert calls == 2


def test_negative_retry_after_uses_a_short_local_cooldown():
    class FakeClock:
        now = 10.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "-1"}, json={"error": {}})

    client = client_for(handler, clock=clock, default_rate_limit_cooldown_seconds=5)

    with pytest.raises(SpotifyApiError) as first_error:
        client.get_devices("access-token")
    assert first_error.value.retry_after_seconds is None

    with pytest.raises(SpotifyApiError) as second_error:
        client.get_devices("access-token")
    assert second_error.value.retry_after_seconds == 5
    assert calls == 1


def test_retry_after_is_capped_at_one_hour():
    class FakeClock:
        now = 10.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    client = client_for(
        lambda _request: httpx.Response(429, headers={"Retry-After": "999999"}, json={"error": {}}),
        clock=clock,
    )

    with pytest.raises(SpotifyApiError):
        client.get_devices("access-token")
    with pytest.raises(SpotifyApiError) as error:
        client.get_devices("access-token")

    assert error.value.retry_after_seconds == 3600


def test_api_cooldown_does_not_block_oauth_refresh_after_a_401_path():
    class FakeClock:
        now = 100.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(429, headers={"Retry-After": "30"}, json={"error": {"reason": "QUOTA_EXCEEDED"}})
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "refreshed", "expires_in": 3600})
        raise AssertionError(request.url)

    client = client_for(handler, clock=clock)

    with pytest.raises(SpotifyApiError) as error:
        client.get_devices("access-token")
    assert error.value.status_code == 429

    assert client.refresh_token("client-id", "refresh-token") == {
        "access_token": "refreshed",
        "expires_in": 3600,
    }
    assert calls == ["/v1/me/player/devices", "/api/token"]


def test_non_rate_limit_errors_do_not_start_provider_cooldown():
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(401, json={"error": {"reason": "TOKEN_EXPIRED"}})
        return httpx.Response(200, json={"devices": []})

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as error:
        client.get_devices("access-token")
    assert error.value.status_code == 401
    assert client.get_devices("access-token") == []
    assert calls == 2


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


@pytest.mark.parametrize("enabled, expected_state", [(True, "true"), (False, "false")])
def test_shuffle_uses_fixed_boolean_state_endpoint_without_request_body(enabled, expected_state):
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        assert request.method == "PUT"
        assert request.url.path == "/v1/me/player/shuffle"
        assert request.url.params["state"] == expected_state
        assert request.url.params["device_id"] == "pc"
        assert request.content == b""
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(204)

    client = client_for(handler)

    client.set_shuffle("access-token", enabled, device_id="pc")

    with pytest.raises(ValueError):
        client.set_shuffle("access-token", 1, device_id="pc")
    assert len(requests) == 1


@pytest.mark.parametrize("mode", ["off", "track", "context"])
def test_repeat_uses_fixed_closed_state_endpoint(mode):
    def handler(request: httpx.Request):
        assert request.method == "PUT"
        assert request.url.path == "/v1/me/player/repeat"
        assert request.url.params["state"] == mode
        assert request.url.params["device_id"] == "pc"
        assert request.content == b""
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(204)

    client = client_for(handler)

    client.set_repeat("access-token", mode, device_id="pc")


def test_repeat_rejects_free_form_state_before_transport():
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(204)

    client = client_for(handler)

    with pytest.raises(ValueError):
        client.set_repeat("access-token", "playlist", device_id="pc")

    assert calls == 0


@pytest.mark.parametrize("status_code", [401, 403, 429])
def test_shuffle_surfaces_fixed_endpoint_http_failures_without_fallback(status_code):
    def handler(_request: httpx.Request):
        headers = {"Retry-After": "4"} if status_code == 429 else None
        return httpx.Response(status_code, headers=headers, json={"error": {"reason": "RATE_LIMITED"}})

    client = client_for(handler)

    with pytest.raises(SpotifyApiError) as error:
        client.set_shuffle("access-token", False, device_id="pc")

    assert error.value.status_code == status_code
    if status_code == 429:
        assert error.value.retry_after_seconds == 4
    assert "access-token" not in str(error.value)
