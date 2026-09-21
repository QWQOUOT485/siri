"""Deterministic, conservative application-name matching."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .app_models import AppEntry, AppType, LaunchMethod, MatchCandidate, MatchResult
from .chinese import normalize_chinese_text


_PUNCTUATION = re.compile(r"[^\w\u3400-\u9fff]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_name(value: str) -> str:
    """Normalize case, punctuation, hyphens, and duplicate whitespace."""

    value = unicodedata.normalize("NFKC", value or "").strip().casefold()
    value = value.replace("_", " ").replace("-", " ")
    value = _PUNCTUATION.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def normalize_app_name(value: str) -> str:
    """Normalize an application/entity name, including Chinese script variants."""

    return normalize_name(normalize_chinese_text(value or ""))


BUILTIN_ALIASES: dict[str, tuple[str, ...]] = {
    "task manager": ("工作管理員", "工作管理员", "taskmgr"),
    "notepad": ("記事本", "记事本"),
    "calculator": ("計算機", "计算器", "小算盤", "小算盘", "calc"),
    "file explorer": ("檔案總管", "文件總管", "文件管理器", "explorer"),
    "settings": ("設定", "设置", "windows 設定", "windows 设置"),
    "windows terminal": ("終端機", "终端机", "terminal", "wt"),
    "command prompt": ("命令提示字元", "命令提示符", "cmd"),
    "control panel": ("控制台", "控制面板", "control"),
    "windows powershell": ("powershell", "power shell"),
    "visual studio code": ("vscode", "vs code", "code"),
    "google chrome": ("chrome", "google chrome"),
    "microsoft edge": ("edge", "microsoft edge"),
    "adobe photoshop": ("photoshop", "adobe photoshop", "ps"),
}


def aliases_for(display_name: str, aliases: Iterable[str] = ()) -> tuple[str, ...]:
    """Merge configured aliases with stable built-in aliases."""

    values = [*aliases, *BUILTIN_ALIASES.get(normalize_app_name(display_name), ())]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_app_name(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


@dataclass(frozen=True)
class _Scored:
    entry: AppEntry
    score: float
    matched_by: str


def _launch_preference(entry: AppEntry) -> tuple[int, int, int]:
    """Prefer a uniquely identifiable executable over wrappers and packages.

    Same-name entries are common on Windows: Start Menu may expose both an
    updater and the real executable, while AppsFolder may expose a packaged
    registration for the same product.  Only a clear executable identity gets
    to break that tie; otherwise matching remains deliberately ambiguous.
    """

    direct_executable = 0
    if entry.launch_method is LaunchMethod.EXECUTABLE and entry.executable_path:
        executable_stem = normalize_app_name(Path(entry.executable_path).stem)
        if executable_stem == normalize_app_name(entry.normalized_name):
            direct_executable = 3
        elif entry.process and entry.process.reliable:
            direct_executable = 1
    process_identity = 1 if entry.process and entry.process.reliable else 0
    system_entry = 1 if entry.app_type is AppType.SYSTEM else 0
    return direct_executable, system_entry, process_identity


def _score(query: str, entry: AppEntry) -> _Scored | None:
    fields: list[tuple[str, str]] = [(normalize_app_name(entry.normalized_name), "name")]
    fields.extend((normalize_app_name(alias), "alias") for alias in entry.aliases)
    best: tuple[float, str] | None = None
    query_tokens = query.split()
    for field, kind in fields:
        if not field:
            continue
        if field == query:
            score = 1.0 if kind == "alias" else 0.99
            method = "exact_alias" if kind == "alias" else "exact_name"
        elif field.startswith(query) or query.startswith(field):
            score = 0.93 if kind == "alias" else 0.91
            method = "prefix_alias" if kind == "alias" else "prefix_name"
        elif query_tokens and all(token in field.split() for token in query_tokens):
            score = 0.88
            method = "token"
        else:
            ratio = difflib.SequenceMatcher(None, query, field).ratio()
            if ratio < 0.56:
                continue
            score = min(0.86, 0.54 + ratio * 0.32)
            method = "fuzzy_alias" if kind == "alias" else "fuzzy_name"
        if best is None or score > best[0]:
            best = (score, method)
    return _Scored(entry, *best) if best else None


def match_app(query: str, entries: Iterable[AppEntry], *, limit: int = 8) -> MatchResult:
    normalized = normalize_app_name(query)
    if not normalized:
        return MatchResult(query=query, candidates=[], ambiguous=False)
    scored = [result for entry in entries if (result := _score(normalized, entry))]
    scored = [result for result in scored if result.score >= 0.60]
    scored.sort(
        key=lambda item: (
            -item.score,
            *(-value for value in _launch_preference(item.entry)),
            normalize_app_name(item.entry.display_name),
            item.entry.app_id,
        )
    )
    selected = scored[:limit]
    candidates = [
        MatchCandidate(
            app_id=item.entry.app_id,
            display_name=item.entry.display_name,
            score=round(item.score, 4),
            matched_by=item.matched_by,
            launchable=item.entry.launchable,
        )
        for item in selected
    ]
    if not selected:
        return MatchResult(query=query, candidates=[], ambiguous=False)
    top = selected[0]
    close_competitors = [item for item in selected[1:] if top.score - item.score <= 0.06]
    top_preference = _launch_preference(top.entry)
    competitor_preference = max((_launch_preference(item.entry) for item in close_competitors), default=(-1, -1, -1))
    ambiguous = bool(close_competitors and top_preference <= competitor_preference)
    return MatchResult(
        query=query,
        best_match=None if ambiguous else candidates[0],
        candidates=candidates,
        ambiguous=ambiguous,
    )
