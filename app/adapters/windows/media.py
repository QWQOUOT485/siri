"""Best-effort system multimedia key adapter."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from .base import OperationResult


_ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]


class WindowsMediaController:
    _keys = {
        "play_pause": 0xB3,
        "play": 0xB3,
        "pause": 0xB3,
        "next": 0xB0,
        "previous": 0xB1,
    }

    def send(self, action: str) -> OperationResult:
        if action not in self._keys:
            return OperationResult(False, "Unsupported media action", "INVALID_MEDIA_ACTION")
        if sys.platform != "win32":
            return OperationResult(False, "Media control is available only on Windows", "WINDOWS_ONLY")
        from .system import WindowsSystemController

        if not WindowsSystemController().session_info().get("interactive"):
            return OperationResult(False, "Agent 不在目前登入的互動式桌面工作階段，拒絕控制媒體。", "NON_INTERACTIVE_SESSION")
        try:
            self._send_key(self._keys[action])
            return OperationResult(True, "已切換播放狀態。" if action in {"play", "pause", "play_pause"} else "已切換曲目。", best_effort=True)
        except (OSError, TypeError, ctypes.ArgumentError):
            return OperationResult(False, "Windows media control failed", "MEDIA_CONTROL_FAILED", best_effort=True)

    @staticmethod
    def _send_key(virtual_key: int) -> None:
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002

        input_array_type = _INPUT * 2
        inputs = input_array_type()
        inputs[0].type = 1
        inputs[0].ki = _KEYBDINPUT(virtual_key, 0, 0, 0, 0)
        inputs[1].type = 1
        inputs[1].ki = _KEYBDINPUT(virtual_key, 0, KEYEVENTF_KEYUP, 0, 0)
        send_input = user32.SendInput
        try:
            send_input.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
            send_input.restype = wintypes.UINT
        except AttributeError:
            # Test doubles and non-Windows shims do not expose ctypes metadata.
            pass
        sent = send_input(len(inputs), ctypes.byref(inputs), ctypes.sizeof(_INPUT))
        if sent != 2:
            raise OSError("SendInput did not send the complete key sequence")
