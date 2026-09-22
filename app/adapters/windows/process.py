"""Current-session process resolver with graceful-close-first behavior."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from app.domain.app_models import ProcessSpec

from .base import OperationResult


class WindowsProcessController:
    WM_CLOSE = 0x0010
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_TERMINATE = 0x0001
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102
    WAIT_FAILED = 0xFFFFFFFF

    def close(self, process: ProcessSpec, *, force: bool = False) -> OperationResult:
        if not process.reliable or not process.executable_names:
            return OperationResult(False, "找得到這個應用程式，但目前無法安全判斷應關閉哪個程序。", "UNSAFE_PROCESS_MAPPING")
        if sys.platform != "win32":
            return OperationResult(False, "Process control is available only on Windows", "WINDOWS_ONLY")
        targets = self._find_windowed_processes(process)
        if not targets:
            return OperationResult(False, "目前找不到這個應用程式的可關閉視窗。", "APP_NOT_RUNNING")
        unique_pids = list(dict.fromkeys(pid for pid, _ in targets))
        if force:
            closed = sum(1 for pid in unique_pids if self._terminate(pid))
            return OperationResult(bool(closed), "已嘗試強制結束程序。" if closed else "無法強制結束程序。", None if closed else "FORCE_CLOSE_FAILED", {"count": closed})

        kernel32 = ctypes.windll.kernel32
        handles: dict[int, int] = {}
        try:
            # Keep one synchronization handle per verified PID.  Reopening by
            # numeric PID after WM_CLOSE cannot distinguish an exited process
            # from an access/inspection failure and is vulnerable to PID reuse.
            for pid in unique_pids:
                handle = kernel32.OpenProcess(self.SYNCHRONIZE, False, pid)
                if not handle:
                    return OperationResult(
                        False,
                        "無法可靠檢查程式狀態，未送出正常關閉要求。",
                        "GRACEFUL_CLOSE_INSPECTION_FAILED",
                        {"remaining": len(unique_pids)},
                    )
                handles[pid] = handle

            remaining = set(unique_pids)
            for pid in tuple(remaining):
                status = self._wait_status(kernel32, handles[pid])
                if status == self.WAIT_OBJECT_0:
                    remaining.discard(pid)
                elif status == self.WAIT_TIMEOUT:
                    continue
                else:
                    return OperationResult(
                        False,
                        "無法可靠檢查程式狀態，未回報正常關閉成功。",
                        "GRACEFUL_CLOSE_INSPECTION_FAILED",
                        {"remaining": len(remaining)},
                    )

            user32 = ctypes.windll.user32
            for pid, hwnd in targets:
                if pid in remaining:
                    user32.PostMessageW(hwnd, self.WM_CLOSE, 0, 0)

            deadline = time.monotonic() + 5.0
            while remaining and time.monotonic() < deadline:
                for pid in tuple(remaining):
                    status = self._wait_status(kernel32, handles[pid])
                    if status == self.WAIT_OBJECT_0:
                        remaining.discard(pid)
                    elif status == self.WAIT_TIMEOUT:
                        continue
                    else:
                        return OperationResult(
                            False,
                            "無法可靠檢查程式狀態，未回報正常關閉成功。",
                            "GRACEFUL_CLOSE_INSPECTION_FAILED",
                            {"remaining": len(remaining)},
                        )
                if remaining:
                    time.sleep(0.1)
            if remaining:
                return OperationResult(False, "已送出正常關閉要求，但程式仍在執行。", "GRACEFUL_CLOSE_TIMEOUT", {"remaining": len(remaining)})
            return OperationResult(True, "已正常關閉程式。", data={"count": len(unique_pids)})
        finally:
            for handle in handles.values():
                kernel32.CloseHandle(handle)

    def _find_windowed_processes(self, process: ProcessSpec) -> list[tuple[int, int]]:
        if sys.platform != "win32":
            return []
        names = {name.casefold() for name in process.executable_names}
        session_id = self._current_session_id()
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        result: list[tuple[int, int]] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            candidate_session = self._process_session_id(int(pid.value))
            if candidate_session != session_id:
                return True
            path = self._process_path(int(pid.value))
            if path and path.name.casefold() in names:
                result.append((int(pid.value), int(hwnd)))
            return True

        user32.EnumWindows(callback, 0)
        return list(dict.fromkeys(result))

    @staticmethod
    def _current_session_id() -> int:
        return WindowsProcessController._process_session_id(ctypes.windll.kernel32.GetCurrentProcessId())

    @staticmethod
    def _process_session_id(pid: int) -> int:
        session = wintypes.DWORD()
        if ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session)):
            return int(session.value)
        return -1

    def _process_path(self, pid: int):
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                from pathlib import Path

                return Path(buffer.value)
        finally:
            kernel32.CloseHandle(handle)
        return None

    @staticmethod
    def _wait_status(kernel32, handle: int) -> int:
        """Return a normalized WaitForSingleObject status for a process handle."""

        # WaitForSingleObject returns a DWORD; masking also handles a test
        # double or an untyped ctypes binding that exposes WAIT_FAILED as -1.
        return int(kernel32.WaitForSingleObject(handle, 0)) & 0xFFFFFFFF

    def _terminate(self, pid: int) -> bool:
        handle = ctypes.windll.kernel32.OpenProcess(self.PROCESS_TERMINATE | self.SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return bool(ctypes.windll.kernel32.TerminateProcess(handle, 1))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
