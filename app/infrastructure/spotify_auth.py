"""Local Spotify Authorization Code with PKCE and token lifecycle."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlparse

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_SPOTIFY_SCOPES = (
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-library-read",
    "user-top-read",
    "user-read-recently-played",
)


class SpotifyAuthError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class SpotifyToken(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    access_token: str = Field(min_length=1, max_length=4096)
    refresh_token: str | None = Field(default=None, min_length=1, max_length=4096)
    expires_at: float = Field(ge=0)
    scope: str = Field(default="", max_length=1000)
    token_type: str = Field(default="Bearer", min_length=1, max_length=50)

    @classmethod
    def from_response(cls, response: dict[str, Any], *, now: float, existing_refresh_token: str | None = None) -> "SpotifyToken":
        access_token = str(response.get("access_token", "")).strip()
        if not access_token:
            raise SpotifyAuthError("SPOTIFY_AUTH_INVALID_RESPONSE", "Spotify 授權回應缺少 access token。")
        try:
            expires_in = max(1, int(response.get("expires_in", 3600)))
        except (TypeError, ValueError):
            expires_in = 3600
        refresh_value = str(response.get("refresh_token", "")).strip() or existing_refresh_token
        return cls(
            access_token=access_token,
            refresh_token=refresh_value,
            expires_at=now + expires_in,
            scope=str(response.get("scope", "")).strip(),
            token_type=str(response.get("token_type", "Bearer")).strip() or "Bearer",
        )


class SpotifyTokenStore:
    """A local-only JSON store; it has no remote/API serialization interface."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> SpotifyToken | None:
        try:
            return SpotifyToken.model_validate(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    def save(self, token: SpotifyToken) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
                json.dump(token.model_dump(mode="json"), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                temporary = Path(handle.name)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink(missing_ok=True)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class SpotifyAuthManager:
    """Small interface hiding PKCE state, local storage, and token refresh."""

    def __init__(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        token_store: SpotifyTokenStore,
        client,
        scopes: tuple[str, ...] = DEFAULT_SPOTIFY_SCOPES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client_id = client_id.strip()
        self.redirect_uri = redirect_uri.strip()
        self.token_store = token_store
        self.client = client
        self.scopes = scopes
        self.clock = clock
        self._pending_state: str | None = None
        self._pending_verifier: str | None = None

    def begin_authorization(self) -> tuple[str, str]:
        if not self.client_id:
            raise SpotifyAuthError("SPOTIFY_NOT_CONFIGURED", "尚未設定 Spotify Client ID。")
        redirect = urlparse(self.redirect_uri)
        if redirect.scheme != "http" or redirect.hostname != "127.0.0.1" or not redirect.path:
            raise SpotifyAuthError("SPOTIFY_REDIRECT_URI_INVALID", "Spotify Redirect URI 必須使用 127.0.0.1 的 loopback 位址。")
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        self._pending_state = state
        self._pending_verifier = verifier
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "scope": " ".join(self.scopes),
        }
        return f"https://accounts.spotify.com/authorize?{urlencode(params)}", state

    def complete_authorization(self, *, code: str, state: str) -> SpotifyToken:
        pending_state = self._pending_state
        verifier = self._pending_verifier
        self._pending_state = None
        self._pending_verifier = None
        if not pending_state or not verifier or not hmac.compare_digest(pending_state, state):
            raise SpotifyAuthError("SPOTIFY_STATE_INVALID", "Spotify 授權狀態無效，請重新開始授權。")
        try:
            response = self.client.exchange_code(self.client_id, code, self.redirect_uri, verifier)
            token = SpotifyToken.from_response(response, now=self.clock())
        except SpotifyAuthError:
            raise
        except Exception as exc:
            raise SpotifyAuthError("SPOTIFY_AUTH_FAILED", "Spotify 授權失敗，請稍後再試。") from exc
        self.token_store.save(token)
        return token

    def get_access_token(self) -> str:
        token = self.token_store.load()
        if token is None:
            raise SpotifyAuthError("SPOTIFY_AUTH_REQUIRED", "請先在 Windows Agent 完成 Spotify 授權。")
        if token.expires_at > self.clock() + 60:
            return token.access_token
        return self.refresh_access_token(existing=token)

    def refresh_access_token(self, *, existing: SpotifyToken | None = None) -> str:
        token = existing or self.token_store.load()
        if token is None or not token.refresh_token:
            self.token_store.clear()
            raise SpotifyAuthError("SPOTIFY_AUTH_REQUIRED", "Spotify 授權已失效，請重新授權。")
        try:
            response = self.client.refresh_token(self.client_id, token.refresh_token)
            refreshed = SpotifyToken.from_response(response, now=self.clock(), existing_refresh_token=token.refresh_token)
        except Exception as exc:
            self.token_store.clear()
            raise SpotifyAuthError("SPOTIFY_AUTH_REQUIRED", "Spotify 授權已失效，請重新授權。") from exc
        self.token_store.save(refreshed)
        return refreshed.access_token

    def safe_status(self) -> dict[str, Any]:
        token = self.token_store.load()
        if token is None:
            return {"authorized": False}
        return {"authorized": True, "expires_at": token.expires_at, "scope": token.scope}
