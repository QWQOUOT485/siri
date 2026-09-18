"""Interactive-session-aware system operations."""

from __future__ import annotations

import ctypes
import getpass
import os
import subprocess
import sys
from ctypes import wintypes

from .base import OperationResult


class WindowsSystemController:
    def session_info(self) -> dict[str, object]:
        user = getpass.getuser()
        if sys.platform != "win32":
            return {"interactive": True, "session_id": None, "user": user, "warning": None}
        session = wintypes.DWORD()
        ok = bool(ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)))
        session_id = int(session.value) if ok else None
        active = int(ctypes.windll.kernel32.WTSGetActiveConsoleSessionId())
        system_user = user.casefold() in {"system", "local service", "network service"}
        interactive = bool(ok and not system_user and session_id not in {None, 0} and (active == 0xFFFFFFFF or session_id == active))
        warning = None if interactive else "Agent is not in the current interactive desktop session; GUI launch may be abnormal."
        return {"interactive": interactive, "session_id": session_id, "user": user, "warning": warning}

    def lock(self) -> OperationResult:
        if sys.platform != "win32":
            return OperationResult(False, "Lock is available only on Windows", "WINDOWS_ONLY")
        if ctypes.windll.user32.LockWorkStation():
            return OperationResult(True, "已鎖定電腦。")
        return OperationResult(False, "Windows 無法鎖定電腦。", "LOCK_FAILED")

    def shutdown(self) -> OperationResult:
        if sys.platform != "win32":
            return OperationResult(False, "Shutdown is available only on Windows", "WINDOWS_ONLY")
        try:
            subprocess.Popen(["shutdown.exe", "/s", "/t", "0"], shell=False, close_fds=True)
            return OperationResult(True, "已送出關機要求。")
        except OSError as exc:
            return OperationResult(False, "Windows 無法執行關機。", "SHUTDOWN_FAILED", {"detail": str(exc)})
