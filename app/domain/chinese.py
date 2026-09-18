"""Deterministic Traditional/Simplified Chinese comparison normalization."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

try:
    from opencc import OpenCC
except ImportError:  # pragma: no cover - setup installs the declared dependency
    OpenCC = None  # type: ignore[assignment,misc]


# This fallback keeps diagnostics usable before dependencies are installed.  The
# production path uses OpenCC's phrase-aware conversion table.
_FALLBACK_TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "倫": "伦",
        "葉": "叶",
        "聽": "听",
        "媽": "妈",
        "後": "后",
        "來": "来",
        "專": "专",
        "輯": "辑",
        "現": "现",
        "場": "场",
        "會": "会",
        "錄": "录",
        "樂": "乐",
        "華": "华",
        "國": "国",
        "開": "开",
        "關": "关",
        "閉": "闭",
        "進": "进",
        "點": "点",
        "選": "选",
        "擇": "择",
        "這": "这",
        "個": "个",
        "發": "发",
        "時": "时",
        "間": "间",
        "聲": "声",
        "說": "说",
        "話": "话",
        "語": "语",
        "嗎": "吗",
        "誰": "谁",
        "麼": "么",
        "無": "无",
        "與": "与",
        "聖": "圣",
        "級": "级",
        "總": "总",
        "體": "体",
        "標": "标",
        "題": "题",
        "類": "类",
        "別": "别",
        "庫": "库",
        "線": "线",
        "網": "网",
        "頁": "页",
        "軟": "软",
        "體": "体",
    }
)


@lru_cache(maxsize=1)
def _converter():
    if OpenCC is None:
        return None
    return OpenCC("t2s")


def normalize_chinese_text(value: str) -> str:
    """Return a stable comparison key without changing display metadata."""

    normalized = unicodedata.normalize("NFKC", value)
    converter = _converter()
    normalized = converter.convert(normalized) if converter is not None else normalized.translate(
        _FALLBACK_TRADITIONAL_TO_SIMPLIFIED
    )
    normalized = normalized.casefold()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())
