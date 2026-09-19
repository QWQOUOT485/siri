"""Deterministic grounding of Local AI slots to the original utterance."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.domain.chinese import normalize_chinese_text
from app.domain.local_ai import GroundedAIIntent, RawAIIntent


_FORBIDDEN_AUTHORITY_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"spotify\s*:\s*(?:track|album|artist)\s*:", re.IGNORECASE),
    re.compile(r"(?:^|\b)(?:powershell|pwsh)(?:\.exe)?(?:\b|\s*-)", re.IGNORECASE),
    re.compile(r"(?:^|\b)cmd(?:\.exe)?(?:\b|\s*/)", re.IGNORECASE),
    re.compile(r"(?:^|\b)python(?:\.exe)?(?:\b|\s*-)", re.IGNORECASE),
    re.compile(r"(?:^|\b)(?:shutdown|rm|del|format)(?:\b|\s+/)", re.IGNORECASE),
    re.compile(r"\b(?:shell|exec(?:ute)?|command)\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z]:[\\/]"),
    re.compile(r"[;&|`$<>]"),
)

_LEFT_BOUNDARY_MARKERS = (
    "我要聽", "我要听", "想聽", "想听", "幫我放", "帮我放", "請播放", "请播放",
    "播放音樂", "播放音乐", "播放", "listen", "play", "聽", "听", "播", "放",
    "的", "專輯", "专辑", "裡面", "里面", "那首", "那個", "那个", "幫我", "帮我",
    "一首", "幫我放一下", "帮我放一下", "播放一下", "播一下", "放一下", "by", "from",
)
_RIGHT_BOUNDARY_MARKERS = (
    "的", "專輯", "专辑", "裡面", "里面", "那首", "歌曲", "歌", "幫我", "帮我",
    "裡的", "里的", "不要", "不是", "by", "from",
)
_UNRESOLVED_REFERENCE_PATTERNS = (
    re.compile(r"(?:那首(?:歌|歌曲)?|那个)$"),
    re.compile(r"(?:的歌|的歌曲)$"),
    re.compile(r"一首(?:好听)?的歌$"),
    re.compile(r"他最红的那首$"),
)


@dataclass(frozen=True)
class GroundingResult:
    accepted: bool
    reason: str
    grounded: GroundedAIIntent | None = None


def canonical(value: str | None) -> str:
    """Create one comparison form without changing user-facing metadata."""

    if not value:
        return ""
    normalized = normalize_chinese_text(unicodedata.normalize("NFKC", value))
    return "".join(char for char in normalized if char.isalnum() or "\u3400" <= char <= "\u9fff").casefold()


_COMMAND_FILLER_SLOTS = frozenset(
    canonical(value) for value in ("一下", "播放一下", "播一下", "放一下")
)


def contains_forbidden_authority(value: str | None) -> bool:
    if not value:
        return False
    return any(pattern.search(value) for pattern in _FORBIDDEN_AUTHORITY_PATTERNS)


def contains_unresolved_reference(value: str | None) -> bool:
    """Reject referential requests that contain no explicit track title."""

    normalized = canonical(value)
    return bool(normalized) and any(pattern.search(normalized) for pattern in _UNRESOLVED_REFERENCE_PATTERNS)


def _is_word_char(char: str) -> bool:
    return bool(char) and (char.isalnum() or "\u3400" <= char <= "\u9fff")


def _ends_with_marker(value: str, markers: tuple[str, ...]) -> bool:
    return any(value.endswith(canonical(marker)) for marker in sorted(markers, key=len, reverse=True))


def _starts_with_marker(value: str, markers: tuple[str, ...]) -> bool:
    return any(value.startswith(canonical(marker)) for marker in sorted(markers, key=len, reverse=True))


def grounded_slot(raw_text: str, proposed: str | None) -> bool:
    """Accept only a complete, deterministic span from the original text."""

    input_text = canonical(raw_text)
    slot = canonical(proposed)
    if not input_text or not slot or slot in _COMMAND_FILLER_SLOTS or contains_forbidden_authority(proposed):
        return False

    start = 0
    while True:
        position = input_text.find(slot, start)
        if position < 0:
            return False
        end = position + len(slot)
        left = input_text[:position]
        right = input_text[end:]
        left_char = input_text[position - 1] if position else ""
        right_char = input_text[end] if end < len(input_text) else ""
        left_word = _is_word_char(left_char)
        right_word = _is_word_char(right_char)
        left_boundary = not left_word or _ends_with_marker(left, _LEFT_BOUNDARY_MARKERS)
        right_boundary = not right_word or _starts_with_marker(right, _RIGHT_BOUNDARY_MARKERS)
        if left_boundary and right_boundary:
            return True
        start = position + 1


class SemanticGrounder:
    """Ground a raw model result without catalog or world-knowledge lookup."""

    def ground(self, original_text: str, raw: RawAIIntent) -> GroundingResult:
        if not original_text or len(original_text) > 300:
            return GroundingResult(False, "input_out_of_bounds")
        if any(ord(char) < 32 or ord(char) == 127 for char in original_text):
            return GroundingResult(False, "control_character")
        if contains_forbidden_authority(original_text):
            return GroundingResult(False, "hostile_input")
        if contains_unresolved_reference(original_text):
            return GroundingResult(False, "unresolved_reference")

        if raw.intent == "unknown":
            return GroundingResult(
                True,
                "accepted_unknown",
                GroundedAIIntent(intent="unknown", track=None, artist=None, album=None),
            )

        if not grounded_slot(original_text, raw.track):
            return GroundingResult(False, "track_not_grounded")

        artist = raw.artist if grounded_slot(original_text, raw.artist) else None
        album = raw.album if grounded_slot(original_text, raw.album) else None
        return GroundingResult(
            True,
            "accepted_grounded_track",
            GroundedAIIntent(intent="spotify_play_track", track=raw.track, artist=artist, album=album),
        )
