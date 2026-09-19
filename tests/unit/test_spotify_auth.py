import json
from urllib.parse import parse_qs, urlparse

import pytest

from app.infrastructure.spotify_auth import SpotifyAuthError, SpotifyAuthManager, SpotifyToken, SpotifyTokenStore


class FakeSpotifyTokenClient:
    def __init__(self):
        self.exchange_calls = []
        self.refresh_calls = []

    def exchange_code(self, client_id, code, redirect_uri, code_verifier):
        self.exchange_calls.append((client_id, code, redirect_uri, code_verifier))
        return {
            "access_token": "access-from-code",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "scope": "user-read-playback-state user-modify-playback-state",
            "token_type": "Bearer",
        }

    def refresh_token(self, client_id, refresh_token):
        self.refresh_calls.append((client_id, refresh_token))
        return {"access_token": "access-refreshed", "expires_in": 3600, "scope": "user-read-playback-state"}


def manager(tmp_path, *, now=1_000.0):
    client = FakeSpotifyTokenClient()
    store = SpotifyTokenStore(tmp_path / "spotify_token.json")
    auth = SpotifyAuthManager(
        client_id="client-id",
        redirect_uri="http://127.0.0.1:8000/spotify/callback",
        token_store=store,
        client=client,
        clock=lambda: now,
    )
    return auth, client, store


def test_pkce_authorization_contains_state_and_challenge_but_not_verifier(tmp_path):
    auth, _, _ = manager(tmp_path)

    authorization_url, state = auth.begin_authorization()

    query = parse_qs(urlparse(authorization_url).query)
    assert query["client_id"] == ["client-id"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/spotify/callback"]
    assert query["state"] == [state]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) >= 40
    assert query["scope"] == [
        "user-modify-playback-state user-read-playback-state user-library-read user-top-read user-read-recently-played"
    ]


def test_pkce_authorization_requests_top_read_only_for_personalization(tmp_path):
    auth, _, _ = manager(tmp_path)

    authorization_url, _ = auth.begin_authorization()

    scopes = set(parse_qs(urlparse(authorization_url).query)["scope"][0].split())

    assert scopes == {
        "user-modify-playback-state",
        "user-read-playback-state",
        "user-library-read",
        "user-top-read",
        "user-read-recently-played",
    }


def test_callback_requires_the_original_state_and_stores_tokens_locally(tmp_path):
    auth, client, store = manager(tmp_path)
    _, state = auth.begin_authorization()

    auth.complete_authorization(code="auth-code", state=state)

    assert client.exchange_calls[0][0:3] == ("client-id", "auth-code", "http://127.0.0.1:8000/spotify/callback")
    assert len(client.exchange_calls[0][3]) >= 43
    saved = store.load()
    assert saved is not None
    assert saved.access_token == "access-from-code"

    with pytest.raises(SpotifyAuthError):
        auth.complete_authorization(code="another-code", state="wrong-state")


def test_expiring_access_token_refreshes_once_without_exposing_tokens_in_status(tmp_path):
    auth, client, store = manager(tmp_path, now=2_000.0)
    store.save(
        SpotifyToken(
            access_token="old-access",
            refresh_token="refresh-token",
            expires_at=2_010.0,
            scope="user-read-playback-state",
            token_type="Bearer",
        )
    )

    assert auth.get_access_token() == "access-refreshed"
    assert client.refresh_calls == [("client-id", "refresh-token")]
    status = auth.safe_status()
    assert status["authorized"] is True
    assert "access_token" not in json.dumps(status)
    assert "refresh_token" not in json.dumps(status)
