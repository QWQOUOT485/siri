"""Master-volume adapter with pycaw precision and media-key fallback."""

from __future__ import annotations

import sys

from .base import OperationResult
from .media import WindowsMediaController


class WindowsVolumeController:
    def __init__(self, *, step: float = 0.05) -> None:
        self.step = max(0.01, min(0.25, float(step)))
        self._media = WindowsMediaController()

    def change(self, action: str, steps: int = 1) -> OperationResult:
        if steps < 1 or steps > 10:
            return OperationResult(False, "音量步數必須介於 1 到 10。", "INVALID_VOLUME_STEPS")
        if sys.platform != "win32":
            return OperationResult(False, "Volume control is available only on Windows", "WINDOWS_ONLY")
        from .system import WindowsSystemController

        if not WindowsSystemController().session_info().get("interactive"):
            return OperationResult(False, "Agent 不在目前登入的互動式桌面工作階段，拒絕控制音量。", "NON_INTERACTIVE_SESSION")
        try:
            endpoint = self._endpoint()
        except Exception:
            endpoint = None
        if endpoint is not None:
            try:
                if action == "volume_up":
                    value = min(1.0, endpoint.GetMasterVolumeLevelScalar() + self.step * steps)
                    endpoint.SetMasterVolumeLevelScalar(value, None)
                    return OperationResult(True, "音量已提高。", data={"level": round(value, 3)})
                if action == "volume_down":
                    value = max(0.0, endpoint.GetMasterVolumeLevelScalar() - self.step * steps)
                    endpoint.SetMasterVolumeLevelScalar(value, None)
                    return OperationResult(True, "音量已降低。", data={"level": round(value, 3)})
                if action == "mute":
                    endpoint.SetMute(1, None)
                    return OperationResult(True, "已靜音。")
                if action == "unmute":
                    endpoint.SetMute(0, None)
                    return OperationResult(True, "已取消靜音。")
                if action == "toggle_mute":
                    endpoint.SetMute(0 if endpoint.GetMute() else 1, None)
                    return OperationResult(True, "已切換靜音狀態。")
            except Exception:
                # Fall through to the system multimedia key fallback.
                pass
        fallback = {"volume_up": "volume_up", "volume_down": "volume_down", "mute": "mute", "unmute": "mute", "toggle_mute": "mute"}.get(action)
        if fallback:
            try:
                key_events = steps if action in {"volume_up", "volume_down"} else 1
                virtual_key = {"volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD}[fallback]
                for _ in range(key_events):
                    self._media._send_key(virtual_key)
                message = "已送出系統音量按鍵。"
                if action == "unmute":
                    message = "已送出取消靜音按鍵（系統按鍵模式為 best-effort）。"
                return OperationResult(True, message, best_effort=True)
            except OSError:
                return OperationResult(False, "Windows 音量控制失敗。", "VOLUME_CONTROL_FAILED", best_effort=True)
        return OperationResult(False, "Unsupported volume action", "INVALID_VOLUME_ACTION")

    def set_volume(self, volume_percent: int) -> OperationResult:
        """Set the Windows master endpoint to an exact scalar percentage.

        This path is intentionally separate from relative media-key fallback:
        a media key cannot guarantee an arbitrary target percentage.
        """

        if isinstance(volume_percent, bool) or not isinstance(volume_percent, int) or not 0 <= volume_percent <= 100:
            return OperationResult(False, "音量百分比必須介於 0 到 100。", "INVALID_VOLUME_PERCENT")
        if sys.platform != "win32":
            return OperationResult(False, "Volume control is available only on Windows", "WINDOWS_ONLY")
        from .system import WindowsSystemController

        if not WindowsSystemController().session_info().get("interactive"):
            return OperationResult(False, "Agent 不在目前登入的互動式桌面工作階段，拒絕控制音量。", "NON_INTERACTIVE_SESSION")
        try:
            endpoint = self._endpoint()
        except Exception:
            return OperationResult(False, "Windows 精確音量控制不可用。", "EXACT_VOLUME_UNAVAILABLE")
        if endpoint is None:
            return OperationResult(False, "Windows 精確音量控制不可用。", "EXACT_VOLUME_UNAVAILABLE")
        scalar = volume_percent / 100.0
        try:
            endpoint.SetMasterVolumeLevelScalar(scalar, None)
        except Exception:
            return OperationResult(False, "Windows 精確音量設定失敗。", "EXACT_VOLUME_SET_FAILED")
        return OperationResult(True, "音量已設定。", data={"level": round(scalar, 3), "volume_percent": volume_percent})

    @staticmethod
    def _endpoint():
        from pycaw.pycaw import AudioUtilities  # type: ignore

        device = AudioUtilities.GetSpeakers()
        return device.EndpointVolume
