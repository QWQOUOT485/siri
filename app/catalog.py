"""In-memory application catalog and safe LaunchSpec construction."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from app.domain.app_models import AppEntry, DiscoveryDiagnostics, LaunchSpec, MatchResult
from app.domain.matching import match_app


class ApplicationCatalog:
    def __init__(self, discovery, cache_path: Path) -> None:
        self.discovery = discovery
        self.cache_path = cache_path
        self._entries: dict[str, AppEntry] = {}
        self._diagnostics = DiscoveryDiagnostics()
        self._last_refresh: str | None = None
        self._lock = RLock()

    def load_cache(self) -> bool:
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            records = raw.get("entries", [])
            entries = [AppEntry.model_validate(item) for item in records]
            with self._lock:
                self._entries = {entry.app_id: entry for entry in entries}
                self._diagnostics = DiscoveryDiagnostics.model_validate(raw.get("diagnostics", {}))
                self._last_refresh = raw.get("last_refresh")
            return bool(entries)
        except (OSError, ValueError, TypeError):
            return False

    def refresh(self) -> tuple[list[AppEntry], DiscoveryDiagnostics]:
        entries, diagnostics = self.discovery.discover()
        with self._lock:
            self._entries = {entry.app_id: entry for entry in entries}
            self._diagnostics = diagnostics
            from datetime import datetime, timezone

            self._last_refresh = datetime.now(timezone.utc).isoformat()
            snapshot = {
                "entries": [entry.model_dump(mode="json") for entry in entries],
                "diagnostics": diagnostics.model_dump(mode="json"),
                "last_refresh": self._last_refresh,
            }
        self._write_cache(snapshot)
        return entries, diagnostics

    def _write_cache(self, snapshot: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.cache_path.parent, delete=False) as handle:
                json.dump(snapshot, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                temporary = Path(handle.name)
            os.replace(temporary, self.cache_path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)  # type: ignore[union-attr]
            except (OSError, UnboundLocalError):
                pass

    def entries(self) -> list[AppEntry]:
        with self._lock:
            return list(self._entries.values())

    def get(self, app_id: str) -> AppEntry | None:
        with self._lock:
            return self._entries.get(app_id)

    def search(self, query: str) -> MatchResult:
        return match_app(query, self.entries())

    @property
    def diagnostics(self) -> DiscoveryDiagnostics:
        with self._lock:
            return self._diagnostics.model_copy(deep=True)

    @property
    def last_refresh(self) -> str | None:
        with self._lock:
            return self._last_refresh

    def launch_spec(self, entry: AppEntry) -> LaunchSpec | None:
        if not entry.launchable or not entry.launch_method or not entry.launch_target:
            return None
        arguments: tuple[str, ...] = ()
        working_directory: str | None = None
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        raw_arguments = metadata.get("arguments", [])
        if isinstance(raw_arguments, list):
            arguments = tuple(str(value)[:512] for value in raw_arguments[:32])
        raw_cwd = metadata.get("working_directory")
        if isinstance(raw_cwd, str) and raw_cwd:
            working_directory = raw_cwd
        return LaunchSpec(
            app_id=entry.app_id,
            method=entry.launch_method,
            target=entry.launch_target,
            arguments=arguments,
            working_directory=working_directory,
            launch_source=entry.launch_source,
            verified=entry.launch_source.value in {"trusted", "manual"},
            executable_path=entry.executable_path,
        )
