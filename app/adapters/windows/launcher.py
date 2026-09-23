"""Safe Windows process and Shell launch adapter."""

from __future__ import annotations

import os
import ntpath
import re
import subprocess
import sys
from pathlib import Path

from app.domain.app_models import LaunchMethod, LaunchSource, LaunchSpec

from .base import OperationResult
from .system_paths import ALLOWED_MSC, trusted_msc_path


class WindowsLauncher:
    """Accept only a catalog-created, verified LaunchSpec."""

    _allowed_shell_prefixes = ("ms-", "shell:AppsFolder\\")
    _allowed_msc = ALLOWED_MSC

    def launch(self, spec: LaunchSpec) -> OperationResult:
        if not isinstance(spec, LaunchSpec) or not spec.verified:
            return OperationResult(False, "Launch target was not verified", "UNVERIFIED_LAUNCH")
        if spec.launch_source not in {LaunchSource.TRUSTED, LaunchSource.MANUAL}:
            return OperationResult(False, "This application has no trusted launch source", "UNTRUSTED_LAUNCH_SOURCE")
        if sys.platform != "win32":
            return OperationResult(False, "Windows launch is available only on Windows", "WINDOWS_ONLY")
        from .system import WindowsSystemController

        session = WindowsSystemController().session_info()
        if not session.get("interactive"):
            return OperationResult(False, "Agent 不在目前登入的互動式桌面工作階段，拒絕啟動 GUI。", "NON_INTERACTIVE_SESSION")
        try:
            if spec.method is LaunchMethod.EXECUTABLE:
                return self._launch_executable(spec)
            if spec.method is LaunchMethod.SHELL_URI:
                if not spec.target.casefold().startswith(tuple(prefix.casefold() for prefix in self._allowed_shell_prefixes)):
                    return OperationResult(False, "Shell target is not an approved Windows URI", "INVALID_SHELL_TARGET")
                os.startfile(spec.target)  # type: ignore[attr-defined]
                return OperationResult(True, "Application started")
            if spec.method is LaunchMethod.SHELL_EXECUTE:
                target = spec.target
                normalized = target.replace("/", "\\")
                basename = ntpath.basename(normalized)
                trusted = trusted_msc_path(basename)
                if (
                    not re.fullmatch(r"[A-Za-z]:\\.+", normalized)
                    or normalized.startswith(("\\\\", "\\?\\", "\\.\\"))
                    or any(part in {".", ".."} for part in normalized.split("\\"))
                    or basename.casefold() not in self._allowed_msc
                    or trusted is None
                    or ntpath.normcase(ntpath.normpath(normalized)) != ntpath.normcase(ntpath.normpath(trusted))
                    or not self._resolved_msc_matches(target, trusted)
                ):
                    return OperationResult(False, "Shell document is not an approved system tool", "INVALID_SYSTEM_TARGET")
                os.startfile(target)  # type: ignore[attr-defined]
                return OperationResult(True, "System tool started")
        except (OSError, PermissionError):
            return OperationResult(False, "Windows could not start the application", "LAUNCH_FAILED")
        return OperationResult(False, "Unsupported launch method", "INVALID_LAUNCH_METHOD")

    @staticmethod
    def _resolved_msc_matches(target: str, trusted: str) -> bool:
        try:
            path = Path(target)
            if not path.is_file():
                return False
            resolved = path.resolve(strict=True)
        except OSError:
            return False
        return ntpath.normcase(ntpath.normpath(str(resolved))) == ntpath.normcase(ntpath.normpath(trusted))

    def _launch_executable(self, spec: LaunchSpec) -> OperationResult:
        target = Path(spec.target)
        if target.suffix.casefold() not in {".exe", ".com"} or not target.is_file():
            return OperationResult(False, "The catalog executable is missing or invalid", "LAUNCH_TARGET_MISSING")
        if spec.executable_path and Path(spec.executable_path).resolve() != target.resolve():
            return OperationResult(False, "Catalog executable identity changed", "LAUNCH_IDENTITY_CHANGED")
        cwd = spec.working_directory
        if cwd and not Path(cwd).is_dir():
            cwd = None
        subprocess.Popen(
            [str(target), *spec.arguments],
            cwd=cwd,
            shell=False,
            close_fds=True,
        )
        return OperationResult(True, "Application started")


class WindowsWebsiteOpener:
    """Open a URL that was already selected from the local website allowlist."""

    def open(self, url: str) -> OperationResult:
        if sys.platform != "win32":
            return OperationResult(False, "Windows website opening is available only on Windows", "WINDOWS_ONLY")
        if not url.startswith("https://"):
            return OperationResult(False, "Website is not in the HTTPS allowlist", "INVALID_WEBSITE")
        from .system import WindowsSystemController

        if not WindowsSystemController().session_info().get("interactive"):
            return OperationResult(False, "Agent 不在目前登入的互動式桌面工作階段，拒絕開啟網站。", "NON_INTERACTIVE_SESSION")
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return OperationResult(True, "Website opened")
        except OSError:
            return OperationResult(False, "Windows could not open the website", "WEBSITE_OPEN_FAILED")
