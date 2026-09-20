"""Small, fixed-endpoint Spotify Web API adapter.

This module deliberately exposes named operations instead of a generic HTTP
proxy.  Remote command text never reaches this adapter as a URL or endpoint.
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Mapping

import httpx


_TRACK_URI = re.compile(r"^spotify:track:[A-Za-z0-9]+$")
_REASON = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_MAX_RETRY_AFTER_SECONDS = 3600
_DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 5


class SpotifyApiError(RuntimeError):
    """An expected Spotify API or network failure without response secrets."""

    def __init__(
        self,
        status_code: int | None,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.reason = reason


class SpotifyApiClient:
    """Adapter for the allowlisted Spotify Accounts and Web API operations."""

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        api_base_url: str = "https://api.spotify.com/v1",
        accounts_base_url: str = "https://accounts.spotify.com",
        clock: Callable[[], float] = time.monotonic,
        default_rate_limit_cooldown_seconds: int = _DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
    ) -> None:
        self.http_client = http_client or httpx.Client(timeout=15.0, follow_redirects=True)
        self.api_base_url = api_base_url.rstrip("/")
        self.accounts_base_url = accounts_base_url.rstrip("/")
        self._clock = clock
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_cooldown_until = 0.0
        self._rate_limit_reason: str | None = None
        self._default_rate_limit_cooldown_seconds = max(0, min(int(default_rate_limit_cooldown_seconds), 60))

    def close(self) -> None:
        self.http_client.close()

    def search_tracks(self, access_token: str, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        payload = self._api_json(
            "GET",
            "/search",
            access_token=access_token,
            params={"q": query, "type": "track", "limit": str(max(1, min(limit, 50)))},
        )
        tracks = payload.get("tracks", {}) if isinstance(payload, dict) else {}
        items = tracks.get("items", []) if isinstance(tracks, dict) else []
        return [item for item in items if isinstance(item, dict)]

    def check_saved_tracks(self, access_token: str, track_uris: Sequence[str]) -> list[bool]:
        """Read Library membership for a bounded set of server-owned track URIs."""

        uris = tuple(track_uris)
        if len(uris) > 3:
            raise ValueError("saved-track lookup is limited to three candidates")
        if any(not isinstance(uri, str) or _TRACK_URI.fullmatch(uri) is None for uri in uris):
            raise ValueError("saved-track lookup accepts Spotify track URIs only")
        if not uris:
            return []
        payload = self._api_value(
            "GET",
            "/me/library/contains",
            access_token=access_token,
            params={"uris": ",".join(uris)},
        )
        if not isinstance(payload, list) or len(payload) != len(uris) or any(not isinstance(value, bool) for value in payload):
            raise SpotifyApiError(200, "Spotify 回應格式無效。")
        return list(payload)

    def get_top_tracks(self, access_token: str, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self._api_json(
            "GET",
            "/me/top/tracks",
            access_token=access_token,
            params={"limit": str(max(1, min(limit, 50)))},
        )
        return self._top_items(payload)

    def get_top_artists(self, access_token: str, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self._api_json(
            "GET",
            "/me/top/artists",
            access_token=access_token,
            params={"limit": str(max(1, min(limit, 50)))},
        )
        return self._top_items(payload)

    def get_recently_played(self, access_token: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Read a bounded list of server-side Recently Played track items."""

        payload = self._api_json(
            "GET",
            "/me/player/recently-played",
            access_token=access_token,
            params={"limit": str(max(1, min(limit, 50)))},
        )
        return self._recent_items(payload)

    def get_devices(self, access_token: str) -> list[dict[str, Any]]:
        payload = self._api_json("GET", "/me/player/devices", access_token=access_token)
        devices = payload.get("devices", []) if isinstance(payload, dict) else []
        return [device for device in devices if isinstance(device, dict)]

    def get_current_playback(self, access_token: str) -> dict[str, Any]:
        """Read the current playback state from the fixed Spotify endpoint."""

        return self._api_json("GET", "/me/player", access_token=access_token)

    def transfer_playback(self, access_token: str, device_id: str, *, play: bool = False) -> None:
        self._api_json(
            "PUT",
            "/me/player",
            access_token=access_token,
            json={"device_ids": [device_id], "play": play},
            allow_non_json_success=True,
        )

    def start_resume(self, access_token: str, *, device_id: str | None = None, track_uri: str | None = None) -> None:
        params = {"device_id": device_id} if device_id else None
        body = {"uris": [track_uri]} if track_uri else None
        self._api_json("PUT", "/me/player/play", access_token=access_token, params=params, json=body, allow_non_json_success=True)

    def pause(self, access_token: str, *, device_id: str | None = None) -> None:
        self._api_json("PUT", "/me/player/pause", access_token=access_token, params=self._device_params(device_id), allow_non_json_success=True)

    def next(self, access_token: str, *, device_id: str | None = None) -> None:
        self._api_json("POST", "/me/player/next", access_token=access_token, params=self._device_params(device_id), allow_non_json_success=True)

    def previous(self, access_token: str, *, device_id: str | None = None) -> None:
        self._api_json("POST", "/me/player/previous", access_token=access_token, params=self._device_params(device_id), allow_non_json_success=True)

    def exchange_code(self, client_id: str, code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
        return self._accounts_json(
            "POST",
            "/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": code_verifier,
            },
        )

    def refresh_token(self, client_id: str, refresh_token: str) -> dict[str, Any]:
        return self._accounts_json(
            "POST",
            "/api/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id},
        )

    @staticmethod
    def _device_params(device_id: str | None) -> Mapping[str, str] | None:
        return {"device_id": device_id} if device_id else None

    @staticmethod
    def _top_items(payload: Any) -> list[dict[str, Any]]:
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise SpotifyApiError(200, "Spotify 回應格式無效。")
        return items

    @staticmethod
    def _recent_items(payload: Any) -> list[dict[str, Any]]:
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or len(items) > 50:
            raise SpotifyApiError(200, "Spotify 回應格式無效。")
        if any(not isinstance(item, dict) or not isinstance(item.get("track"), dict) for item in items):
            raise SpotifyApiError(200, "Spotify 回應格式無效。")
        return items

    def _api_json(self, method: str, path: str, *, access_token: str, allow_non_json_success: bool = False, **kwargs) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {access_token}"
        headers.setdefault("Accept", "application/json")
        return self._request_json(
            method,
            f"{self.api_base_url}{path}",
            headers=headers,
            rate_limit_guard=True,
            allow_non_json_success=allow_non_json_success,
            **kwargs,
        )

    def _api_value(self, method: str, path: str, *, access_token: str, allow_non_json_success: bool = False, **kwargs) -> Any:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {access_token}"
        headers.setdefault("Accept", "application/json")
        return self._request_value(
            method,
            f"{self.api_base_url}{path}",
            headers=headers,
            rate_limit_guard=True,
            allow_non_json_success=allow_non_json_success,
            **kwargs,
        )

    def _accounts_json(self, method: str, path: str, *, data: Mapping[str, str]) -> dict[str, Any]:
        return self._request_json(
            method,
            f"{self.accounts_base_url}{path}",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            rate_limit_guard=False,
            data=data,
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        allow_non_json_success: bool = False,
        rate_limit_guard: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        payload = self._request_value(
            method,
            url,
            headers=headers,
            allow_non_json_success=allow_non_json_success,
            rate_limit_guard=rate_limit_guard,
            **kwargs,
        )
        return payload if isinstance(payload, dict) else {}

    def _request_value(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        allow_non_json_success: bool = False,
        rate_limit_guard: bool = True,
        **kwargs,
    ) -> Any:
        if rate_limit_guard:
            self._raise_if_rate_limited()
        try:
            response = self.http_client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise SpotifyApiError(None, "Spotify 網路連線失敗。") from exc

        if response.status_code >= 400:
            retry_after = self._retry_after(response)
            reason = self._error_reason(response)
            if rate_limit_guard and response.status_code == 429:
                self._record_rate_limit(retry_after, reason)
            messages = {
                401: "Spotify 授權已失效。",
                403: "Spotify 拒絕這項播放操作，請確認 Premium 與帳戶狀態。",
                429: "Spotify 目前請求過多，請稍後再試。",
            }
            raise SpotifyApiError(
                response.status_code,
                messages.get(response.status_code, "Spotify API 請求失敗。"),
                retry_after_seconds=retry_after,
                reason=reason,
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            if allow_non_json_success and 200 <= response.status_code < 300:
                return {}
            raise SpotifyApiError(response.status_code, "Spotify 回應格式無效。") from exc
        return payload

    @staticmethod
    def _retry_after(response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        try:
            parsed = int(value) if value is not None else None
            if parsed is None or parsed < 0:
                return None
            return min(parsed, _MAX_RETRY_AFTER_SECONDS)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _error_reason(response: httpx.Response) -> str | None:
        """Keep only a bounded provider reason; never retain arbitrary error text."""

        try:
            payload = response.json()
        except ValueError:
            return None
        error = payload.get("error") if isinstance(payload, dict) else None
        reason = error.get("reason") if isinstance(error, dict) else None
        if not isinstance(reason, str) or _REASON.fullmatch(reason) is None:
            return None
        return reason

    def _raise_if_rate_limited(self) -> None:
        now = self._clock()
        with self._rate_limit_lock:
            remaining = self._rate_limit_cooldown_until - now
            if remaining <= 0:
                if self._rate_limit_cooldown_until:
                    self._rate_limit_cooldown_until = 0.0
                    self._rate_limit_reason = None
                return
            retry_after = max(1, min(math.ceil(remaining), _MAX_RETRY_AFTER_SECONDS))
            reason = self._rate_limit_reason
        raise SpotifyApiError(
            429,
            "Spotify 目前請求過多，請稍後再試。",
            retry_after_seconds=retry_after,
            reason=reason,
        )

    def _record_rate_limit(self, retry_after: int | None, reason: str | None) -> None:
        cooldown_seconds = retry_after
        if cooldown_seconds is None:
            cooldown_seconds = self._default_rate_limit_cooldown_seconds
        if cooldown_seconds <= 0:
            return
        deadline = self._clock() + min(cooldown_seconds, _MAX_RETRY_AFTER_SECONDS)
        with self._rate_limit_lock:
            if deadline >= self._rate_limit_cooldown_until:
                self._rate_limit_cooldown_until = deadline
            if reason is not None:
                self._rate_limit_reason = reason
