"""Application and website orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.windows.base import OperationResult
from app.catalog import ApplicationCatalog
from app.domain.app_models import AppType, WebsiteEntry
from app.domain.matching import normalize_name


@dataclass(frozen=True)
class WebsiteMatch:
    entry: WebsiteEntry | None
    ambiguous: bool
    candidates: tuple[WebsiteEntry, ...] = ()


class WebsiteCatalog:
    def __init__(self, entries: tuple[WebsiteEntry, ...]) -> None:
        self.entries = entries

    def find(self, query: str | None = None, website_id: str | None = None) -> WebsiteMatch:
        if website_id:
            for entry in self.entries:
                if entry.website_id == website_id:
                    return WebsiteMatch(entry, False, (entry,))
            return WebsiteMatch(None, False, ())
        normalized = normalize_name(query or "")
        if not normalized:
            return WebsiteMatch(None, False, ())
        matches = []
        for entry in self.entries:
            names = {normalize_name(entry.display_name), *(normalize_name(value) for value in entry.aliases)}
            if normalized in names or any(name.startswith(normalized) for name in names):
                matches.append(entry)
        if len(matches) == 1:
            return WebsiteMatch(matches[0], False, tuple(matches))
        return WebsiteMatch(None, bool(matches), tuple(matches))


class ApplicationService:
    def __init__(self, catalog: ApplicationCatalog, launcher, process_controller, website_opener, website_catalog: WebsiteCatalog) -> None:
        self.catalog = catalog
        self.launcher = launcher
        self.process_controller = process_controller
        self.website_opener = website_opener
        self.website_catalog = website_catalog

    def open_app(self, *, app_id: str | None = None, app_query: str | None = None) -> OperationResult:
        entry, ambiguity = self._resolve_app(app_id, app_query)
        if ambiguity:
            return ambiguity
        if entry is None:
            return OperationResult(False, f"找不到 {app_query or app_id}。", "UNKNOWN_APP")
        spec = self.catalog.launch_spec(entry)
        if spec is None:
            return OperationResult(False, "找到這個程式，但它沒有可信任的啟動入口。", "APP_NOT_LAUNCHABLE")
        result = self.launcher.launch(spec)
        if result.success:
            return OperationResult(True, f"已開啟 {entry.display_name}。", data={"app_id": entry.app_id, "display_name": entry.display_name})
        return result

    def close_app(self, *, app_id: str | None = None, app_query: str | None = None, force: bool = False) -> OperationResult:
        entry, ambiguity = self._resolve_app(app_id, app_query)
        if ambiguity:
            return ambiguity
        if entry is None:
            return OperationResult(False, f"找不到 {app_query or app_id}。", "UNKNOWN_APP")
        if entry.app_type is AppType.SYSTEM:
            return OperationResult(False, "Windows 內建工具目前只支援開啟，不執行關閉。", "SYSTEM_APP_CLOSE_UNSUPPORTED")
        if not entry.process or not entry.process.reliable:
            return OperationResult(False, "可以找到這個程式，但無法安全判斷應關閉哪個 process。", "UNSAFE_PROCESS_MAPPING")
        result = self.process_controller.close(entry.process, force=force)
        if result.success:
            result.data.setdefault("app_id", entry.app_id)
        return result

    def open_website(self, *, website_id: str | None = None, website_query: str | None = None) -> OperationResult:
        match = self.website_catalog.find(website_id=website_id, query=website_query)
        if match.ambiguous:
            names = [entry.display_name for entry in match.candidates]
            return OperationResult(False, f"找到多個可能的網站：{'、'.join(names)}。", "AMBIGUOUS_WEBSITE", {"candidates": names})
        if match.entry is None:
            return OperationResult(False, f"找不到網站 {website_query or website_id}。", "UNKNOWN_WEBSITE")
        result = self.website_opener.open(match.entry.url)
        if result.success:
            return OperationResult(True, f"已開啟 {match.entry.display_name}。", data={"website_id": match.entry.website_id})
        return result

    def refresh(self) -> OperationResult:
        try:
            entries, diagnostics = self.catalog.refresh()
            return OperationResult(True, f"已重新掃描程式，找到 {len(entries)} 個項目。", data={"count": len(entries), "warnings": diagnostics.warnings})
        except Exception:
            return OperationResult(False, "程式清單更新失敗，詳細資訊已寫入本機 log。", "CATALOG_UNAVAILABLE")

    def _resolve_app(self, app_id: str | None, app_query: str | None):
        if app_id:
            entry = self.catalog.get(app_id)
            if entry is None:
                return None, None
            return entry, None
        result = self.catalog.search(app_query or "")
        if result.ambiguous:
            names = [candidate.display_name for candidate in result.candidates]
            return None, OperationResult(False, f"找到多個可能的程式：{'、'.join(names)}，請說完整名稱。", "AMBIGUOUS_APP", {"candidates": [candidate.model_dump() for candidate in result.candidates]})
        if result.best_match is None:
            return None, None
        return self.catalog.get(result.best_match.app_id), None
