"""Windows application discovery with explicit source trust boundaries."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.domain.app_models import (
    AppEntry,
    AppType,
    DiscoveryDiagnostics,
    LaunchMethod,
    LaunchSource,
    ProcessSpec,
)
from app.domain.matching import aliases_for, normalize_name

from .base import AdapterError
from .system_apps import stable_app_id, system_app_entries


KNOWN_PATH_EXECUTABLES = {
    "code.exe": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "spotify.exe": "Spotify",
    "vlc.exe": "VLC",
    "obs64.exe": "OBS Studio",
    "steam.exe": "Steam",
}

FIXED_SHORTCUT_SCRIPT = r"""
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
$shell = New-Object -ComObject WScript.Shell
$roots = @(
  [Environment]::GetFolderPath('StartMenu'),
  [Environment]::GetFolderPath('CommonStartMenu'),
  [Environment]::GetFolderPath('Desktop'),
  [Environment]::GetFolderPath('CommonDesktop')
) | Where-Object { $_ } | Sort-Object -Unique
$items = foreach ($root in $roots) {
  Get-ChildItem -LiteralPath $root -Filter '*.lnk' -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    $shortcut = $shell.CreateShortcut($_.FullName)
    [PSCustomObject]@{
      Name = $_.BaseName
      ShortcutPath = $_.FullName
      TargetPath = $shortcut.TargetPath
      Arguments = $shortcut.Arguments
      WorkingDirectory = $shortcut.WorkingDirectory
    }
  }
}
@($items) | ConvertTo-Json -Compress
"""

FIXED_APPS_FOLDER_SCRIPT = r"""
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress
"""


def _is_windows() -> bool:
    return sys.platform == "win32"


def _clean_executable(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parts = shlex.split(raw, posix=False)
        raw = parts[0] if parts else raw
    except ValueError:
        raw = raw.split(" ", 1)[0]
    raw = raw.strip().strip('"').strip()
    return raw or None


def _valid_executable(path_value: str | None) -> Path | None:
    cleaned = _clean_executable(path_value)
    if not cleaned:
        return None
    path = Path(cleaned).expanduser()
    try:
        if path.is_file() and path.suffix.casefold() in {".exe", ".com"}:
            return path.resolve()
    except OSError:
        return None
    return None


def _process_spec(path: Path | None, extra: tuple[str, ...] = ()) -> ProcessSpec | None:
    names = list(extra)
    if path:
        names.append(path.name.casefold())
    unique = tuple(dict.fromkeys(name.casefold() for name in names if name))
    return ProcessSpec(executable_names=unique, reliable=bool(unique)) if unique else None


def _path_entry(
    *,
    display_name: str,
    target: Path,
    source: str,
    aliases: tuple[str, ...] = (),
    app_type: AppType = AppType.DESKTOP,
    shortcut_path: str | None = None,
    arguments: tuple[str, ...] = (),
    working_directory: str | None = None,
    confidence: float = 0.9,
) -> AppEntry:
    return AppEntry(
        app_id=stable_app_id(source, display_name, str(target)),
        display_name=display_name,
        normalized_name=normalize_name(display_name),
        aliases=aliases_for(display_name, aliases),
        launch_method=LaunchMethod.EXECUTABLE,
        launch_target=str(target),
        executable_path=str(target),
        process=_process_spec(target),
        source=source,
        app_type=app_type,
        shortcut_path=shortcut_path,
        confidence=confidence,
        launch_source=LaunchSource.TRUSTED,
        launch_confidence=confidence,
        metadata_confidence=confidence,
        metadata={"arguments": list(arguments), "working_directory": working_directory},
    )


def _json_records(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        return [parsed]
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


class WindowsApplicationDiscovery:
    """Collect only known local sources; never recursively scan a drive."""

    def __init__(self, *, manual_apps: tuple[dict[str, Any], ...] = (), application_aliases: dict[str, tuple[str, ...]] | None = None) -> None:
        self.manual_apps = manual_apps
        self.application_aliases = {normalize_name(key): tuple(values) for key, values in (application_aliases or {}).items()}

    def _run_fixed_powershell(self, script: str) -> str:
        if not _is_windows():
            return ""
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return completed.stdout or ""

    def discover(self) -> tuple[list[AppEntry], DiscoveryDiagnostics]:
        entries: list[AppEntry] = []
        diagnostics = DiscoveryDiagnostics(scanned_sources=[])

        def source(name: str) -> None:
            if name not in diagnostics.scanned_sources:
                diagnostics.scanned_sources.append(name)

        def add(entry: AppEntry) -> None:
            entries.append(entry)
            diagnostics.source_counts[entry.source] = diagnostics.source_counts.get(entry.source, 0) + 1

        for entry in system_app_entries():
            add(entry)
        source("system_apps")

        if not _is_windows():
            diagnostics.warnings.append("Windows discovery sources skipped because this is not Windows")
            return self._deduplicate(self._apply_configured_aliases(entries)), diagnostics

        self._discover_shortcuts(add, diagnostics, source)
        self._discover_app_paths(add, diagnostics, source)
        self._discover_apps_folder(add, diagnostics, source)
        self._discover_path_apps(add, diagnostics, source)
        self._discover_manual_apps(add, diagnostics, source)
        self._discover_metadata(add, diagnostics, source)
        return self._deduplicate(self._apply_configured_aliases(entries)), diagnostics

    def _apply_configured_aliases(self, entries: list[AppEntry]) -> list[AppEntry]:
        if not self.application_aliases:
            return entries
        result: list[AppEntry] = []
        for entry in entries:
            configured = self.application_aliases.get(entry.normalized_name, ())
            if configured:
                result.append(entry.model_copy(update={"aliases": aliases_for(entry.display_name, (*entry.aliases, *configured))}))
            else:
                result.append(entry)
        return result

    def _discover_shortcuts(self, add, diagnostics: DiscoveryDiagnostics, source) -> None:
        source("start_menu_shortcuts")
        records = _json_records(self._run_fixed_powershell(FIXED_SHORTCUT_SCRIPT))
        for record in records:
            target = _valid_executable(str(record.get("TargetPath", "")))
            if not target:
                diagnostics.ignored.append({"source": "start_menu_shortcuts", "reason": "target is not an existing executable"})
                continue
            display_name = str(record.get("Name", target.stem)).strip() or target.stem
            add(
                _path_entry(
                    display_name=display_name,
                    target=target,
                    source="start_menu_shortcuts",
                    shortcut_path=str(record.get("ShortcutPath", "")) or None,
                    confidence=0.92,
                )
            )

    def _registry_roots(self):
        try:
            import winreg  # type: ignore
        except ImportError:
            return []
        roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        views = [0]
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            views.extend([winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY])
        return [(root, view) for root in roots for view in dict.fromkeys(views)]

    def _discover_app_paths(self, add, diagnostics: DiscoveryDiagnostics, source) -> None:
        source("registry_app_paths")
        try:
            import winreg  # type: ignore
        except ImportError:
            return
        key_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
        for root, view in self._registry_roots():
            try:
                with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            child_name = winreg.EnumKey(parent, index)
                            with winreg.OpenKey(parent, child_name) as child:
                                value, _ = winreg.QueryValueEx(child, "")
                            target = _valid_executable(str(value))
                            if not target:
                                diagnostics.ignored.append({"source": "registry_app_paths", "reason": "registry target is not an existing executable"})
                                continue
                            name = Path(child_name).stem or target.stem
                            add(_path_entry(display_name=name, target=target, source="registry_app_paths", aliases=(name,), confidence=0.95))
                        except (OSError, IndexError):
                            continue
            except OSError:
                continue

    def _discover_apps_folder(self, add, diagnostics: DiscoveryDiagnostics, source) -> None:
        source("apps_folder")
        for record in _json_records(self._run_fixed_powershell(FIXED_APPS_FOLDER_SCRIPT)):
            name = str(record.get("Name", "")).strip()
            aumid = str(record.get("AppID", "")).strip()
            if not name or not aumid:
                continue
            aliases = aliases_for(name)
            add(
                AppEntry(
                    app_id=stable_app_id("apps_folder", name, aumid),
                    display_name=name,
                    normalized_name=normalize_name(name),
                    aliases=aliases,
                    launch_method=LaunchMethod.SHELL_URI,
                    launch_target=f"shell:AppsFolder\\{aumid}",
                    process=None,
                    source="apps_folder",
                    app_type=AppType.PACKAGED,
                    aumid=aumid,
                    confidence=0.94,
                    launch_source=LaunchSource.TRUSTED,
                    launch_confidence=0.94,
                    metadata_confidence=0.9,
                )
            )

    def _discover_path_apps(self, add, diagnostics: DiscoveryDiagnostics, source) -> None:
        source("known_path_apps")
        for executable, display_name in KNOWN_PATH_EXECUTABLES.items():
            target_value = shutil.which(executable)
            target = _valid_executable(target_value)
            if target:
                add(_path_entry(display_name=display_name, target=target, source="known_path_apps", aliases=(Path(executable).stem,), confidence=0.8))

    def _discover_manual_apps(self, add, diagnostics: DiscoveryDiagnostics, source) -> None:
        source("manual_apps")
        for item in self.manual_apps:
            target = _valid_executable(str(item.get("path", "")))
            if not target:
                diagnostics.ignored.append({"source": "manual_apps", "reason": "configured path is not an existing .exe/.com"})
                continue
            name = str(item.get("name", target.stem)).strip() or target.stem
            aliases = tuple(str(value) for value in item.get("aliases", []) if str(value).strip())
            add(_path_entry(display_name=name, target=target, source="manual_apps", aliases=aliases, app_type=AppType.PORTABLE, confidence=1.0))

    def _discover_metadata(self, add, diagnostics: DiscoveryDiagnostics, source) -> None:
        source("registry_uninstall_metadata")
        try:
            import winreg  # type: ignore
        except ImportError:
            return
        key_paths = (
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        for root, view in self._registry_roots():
            for key_path in key_paths:
                try:
                    with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as parent:
                        for index in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                subkey = winreg.EnumKey(parent, index)
                                with winreg.OpenKey(parent, subkey) as child:
                                    name = str(winreg.QueryValueEx(child, "DisplayName")[0]).strip()
                                    if not name:
                                        continue
                                    publisher = str(self._query_value(child, winreg, "Publisher") or "")
                                    version = str(self._query_value(child, winreg, "DisplayVersion") or "")
                                    install_location = str(self._query_value(child, winreg, "InstallLocation") or "")
                                add(
                                    AppEntry(
                                        app_id=stable_app_id("registry_uninstall", name, subkey),
                                        display_name=name,
                                        normalized_name=normalize_name(name),
                                        aliases=aliases_for(name),
                                        source="registry_uninstall",
                                        app_type=AppType.METADATA,
                                        launch_source=LaunchSource.METADATA_ONLY,
                                        confidence=0.4,
                                        launch_confidence=0.0,
                                        metadata_confidence=0.8,
                                        metadata={"publisher": publisher, "version": version, "install_location": install_location},
                                    )
                                )
                            except (OSError, IndexError, TypeError):
                                continue
                except OSError:
                    continue

    @staticmethod
    def _query_value(key, winreg, name: str):
        try:
            return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return None

    @staticmethod
    def _deduplicate(entries: list[AppEntry]) -> list[AppEntry]:
        by_key: dict[tuple[str, str, str], AppEntry] = {}
        for entry in entries:
            target = normalize_name(entry.launch_target or "")
            key = (entry.normalized_name, target, entry.launch_source.value)
            existing = by_key.get(key)
            if not existing:
                by_key[key] = entry
                continue
            if entry.launch_confidence > existing.launch_confidence:
                by_key[key] = entry
            elif entry.aliases:
                aliases = tuple(dict.fromkeys((*existing.aliases, *entry.aliases)))
                by_key[key] = existing.model_copy(update={"aliases": aliases})
        deduplicated = list(by_key.values())
        trusted_by_name: dict[str, list[AppEntry]] = {}
        for entry in deduplicated:
            if entry.launch_source in {LaunchSource.TRUSTED, LaunchSource.MANUAL}:
                trusted_by_name.setdefault(entry.normalized_name, []).append(entry)
        merged: list[AppEntry] = []
        for entry in deduplicated:
            trusted = trusted_by_name.get(entry.normalized_name, [])
            if entry.launch_source is LaunchSource.METADATA_ONLY and len(trusted) == 1:
                trusted_entry = trusted[0]
                merged_metadata = {**entry.metadata, **trusted_entry.metadata}
                replacement = trusted_entry.model_copy(update={"metadata": merged_metadata})
                if replacement not in merged:
                    merged.append(replacement)
                continue
            merged.append(entry)
        return sorted(merged, key=lambda item: (item.normalized_name, item.source, item.app_id))
