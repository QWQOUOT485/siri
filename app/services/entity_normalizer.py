"""Deterministic, non-destructive normalization for entity aliases."""

from __future__ import annotations

from app.domain.chinese import normalize_chinese_text
from app.domain.semantic_memory import MAX_ENTITY_TEXT, NormalizedEntityText


class EntityNormalizer:
    """Derive bounded comparison keys while retaining the original utterance."""

    def __init__(self, *, max_length: int = MAX_ENTITY_TEXT) -> None:
        self.max_length = max(1, min(int(max_length), MAX_ENTITY_TEXT))

    def normalize(self, value: str) -> NormalizedEntityText:
        if not isinstance(value, str):
            raise ValueError("entity text must be a string")
        if not value or len(value) > self.max_length:
            raise ValueError("entity text is empty or too long")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("entity text must not contain control characters")

        canonical = normalize_chinese_text(value)
        if not canonical:
            raise ValueError("entity text must contain a comparable value")
        compact = canonical.replace(" ", "")
        return NormalizedEntityText(
            raw=value,
            canonical_text=canonical,
            compact_text=compact,
            chinese_canonical=canonical,
        )
