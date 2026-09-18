"""Spotify Connect device resolution and playback controls."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.adapters.windows.base import OperationResult

from .base import SpotifyDevice
from .catalog import SpotifyTrackRef


class SpotifyPlayer:
    """Deep player interface: resolve a usable Connect device, then control it."""

    def __init__(
        self,
        client,
        *,
        device_name: str = "",
        open_spotify: Callable[[], OperationResult] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        device_retries: int = 3,
        device_wait_seconds: float = 1.0,
    ) -> None:
        self.client = client
        self.device_name = device_name.strip()
        self.open_spotify = open_spotify
        self.sleep = sleep
        self.device_retries = max(0, min(device_retries, 5))
        self.device_wait_seconds = max(0.0, min(device_wait_seconds, 10.0))

    def resume(self, access_token: str, track: SpotifyTrackRef | None = None) -> OperationResult:
        device = self._resolve_device(access_token)
        if device is None:
            return self._missing_device()
        if not device.is_active:
            self.client.transfer_playback(access_token, device.device_id, play=False)
        self.client.start_resume(access_token, device_id=device.device_id, track_uri=track.track_uri if track else None)
        message = f"已在 Spotify 的 {device.name} 恢復播放。"
        if track:
            message = f"已在 Spotify 播放 {track.track_name}。"
        return OperationResult(True, message, data={"device_name": device.name, "track_name": track.track_name if track else None})

    def pause(self, access_token: str) -> OperationResult:
        return self._control(access_token, "pause", "已暫停 Spotify。", transfer_play=False, resume_after=False)

    def next(self, access_token: str) -> OperationResult:
        return self._control(access_token, "next", "已切換到 Spotify 下一首。", transfer_play=True, resume_after=True)

    def previous(self, access_token: str) -> OperationResult:
        return self._control(access_token, "previous", "已切換到 Spotify 上一首。", transfer_play=True, resume_after=True)

    def _control(
        self,
        access_token: str,
        action: str,
        message: str,
        *,
        transfer_play: bool,
        resume_after: bool,
    ) -> OperationResult:
        device = self._resolve_device(access_token)
        if device is None:
            return self._missing_device()
        if not device.is_active:
            self.client.transfer_playback(access_token, device.device_id, play=transfer_play)
        getattr(self.client, action)(access_token, device_id=device.device_id)
        if resume_after:
            self.client.start_resume(access_token, device_id=device.device_id)
        return OperationResult(True, message, data={"device_name": device.name})

    def _resolve_device(self, access_token: str) -> SpotifyDevice | None:
        for attempt in range(self.device_retries + 1):
            devices = self._valid_devices(self.client.get_devices(access_token))
            if devices:
                preferred = self._preferred(devices)
                if preferred is not None:
                    return preferred
            if attempt >= self.device_retries or self.open_spotify is None:
                return None
            opened = self.open_spotify()
            if not opened.success:
                return None
            self.sleep(self.device_wait_seconds)
        return None

    def _preferred(self, devices: list[SpotifyDevice]) -> SpotifyDevice | None:
        if self.device_name:
            wanted = self._normalize(self.device_name)
            for device in devices:
                if self._normalize(device.name) == wanted:
                    return device
            return None
        for device in devices:
            if device.is_active:
                return device
        return devices[0] if devices else None

    @staticmethod
    def _valid_devices(raw_devices) -> list[SpotifyDevice]:
        valid: list[SpotifyDevice] = []
        for raw in raw_devices or []:
            try:
                device = raw if isinstance(raw, SpotifyDevice) else SpotifyDevice.from_payload(raw)
            except Exception:
                continue
            if not device.is_restricted:
                valid.append(device)
        return valid

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @staticmethod
    def _missing_device() -> OperationResult:
        return OperationResult(False, "找不到可用的 Spotify 播放裝置，請先開啟 Spotify Desktop。", "SPOTIFY_DEVICE_NOT_FOUND")
