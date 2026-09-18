"""Spotify intent orchestration behind the command-service seam."""

from __future__ import annotations

from typing import Any, Callable

from app.adapters.spotify.client import SpotifyApiError
from app.adapters.windows.base import OperationResult
from app.domain.actions import ActionName, ValidatedAction
from app.infrastructure.spotify_auth import SpotifyAuthError


class SpotifyService:
    """Resolve safe Spotify actions without exposing tokens or raw API access."""

    def __init__(self, auth, catalog, player) -> None:
        self.auth = auth
        self.catalog = catalog
        self.player = player

    def execute(self, command: ValidatedAction) -> OperationResult:
        if command.action not in {
            ActionName.SPOTIFY_RESUME,
            ActionName.SPOTIFY_PAUSE,
            ActionName.SPOTIFY_NEXT,
            ActionName.SPOTIFY_PREVIOUS,
            ActionName.SPOTIFY_PLAY_TRACK,
        }:
            return OperationResult(False, "不支援這個 Spotify action。", "INVALID_SPOTIFY_ACTION")
        try:
            access_token = self.auth.get_access_token()
        except SpotifyAuthError as exc:
            return OperationResult(False, str(exc), exc.error_code)

        try:
            return self._execute_with_token(command, access_token)
        except SpotifyApiError as exc:
            if exc.status_code == 401:
                try:
                    refreshed_token = self.auth.refresh_access_token()
                except SpotifyAuthError as auth_error:
                    return OperationResult(False, str(auth_error), auth_error.error_code)
                try:
                    return self._execute_with_token(command, refreshed_token)
                except SpotifyApiError as retry_error:
                    return self._api_error(retry_error)
            return self._api_error(exc)

    def _execute_with_token(self, command: ValidatedAction, access_token: str) -> OperationResult:
        if command.action is ActionName.SPOTIFY_RESUME:
            return self.player.resume(access_token)
        if command.action is ActionName.SPOTIFY_PAUSE:
            return self.player.pause(access_token)
        if command.action is ActionName.SPOTIFY_NEXT:
            return self.player.next(access_token)
        if command.action is ActionName.SPOTIFY_PREVIOUS:
            return self.player.previous(access_token)

        resolution = self.catalog.find_track(
            command.track or "",
            command.artist,
            command.album,
            version_hint=command.version_hint,
            access_token=access_token,
        )
        if resolution.track is None:
            if resolution.ambiguous:
                candidates = [self._public_track(candidate) for candidate in resolution.candidates]
                details = []
                if command.album:
                    details.append(f"專輯：{command.album}")
                if command.version_hint:
                    details.append(f"版本：{command.version_hint.value}")
                detail_suffix = f"（{'／'.join(details)}）" if details else ""
                return OperationResult(
                    False,
                    f"找到多個可能的 {command.track}{detail_suffix}，請補充歌手、專輯或版本。",
                    "SPOTIFY_AMBIGUOUS_TRACK",
                    {"candidates": candidates},
                )
            return OperationResult(False, f"Spotify 找不到歌曲 {command.track}。", "SPOTIFY_TRACK_NOT_FOUND")
        result = self.player.resume(access_token, resolution.track)
        if result.success:
            result.data.setdefault("track_name", resolution.track.track_name)
            result.data.setdefault("artist_names", list(resolution.track.artist_names))
            result.data.setdefault("album_name", resolution.track.album_name)
        return result

    @staticmethod
    def _public_track(track) -> dict[str, Any]:
        return {
            "track_id": track.track_id,
            "track_name": track.track_name,
            "artist_names": list(track.artist_names),
            "album_name": track.album_name,
        }

    @staticmethod
    def _api_error(error: SpotifyApiError) -> OperationResult:
        if error.status_code == 403:
            return OperationResult(False, str(error), "SPOTIFY_FORBIDDEN")
        if error.status_code == 429:
            data = {"retry_after_seconds": error.retry_after_seconds} if error.retry_after_seconds is not None else {}
            return OperationResult(False, str(error), "SPOTIFY_RATE_LIMITED", data)
        if error.status_code is None:
            return OperationResult(False, str(error), "SPOTIFY_NETWORK_ERROR")
        return OperationResult(False, str(error), "SPOTIFY_API_ERROR")
