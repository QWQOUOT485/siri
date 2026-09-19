"""Deterministic, non-destructive normalization for entity aliases."""

from __future__ import annotations

import time

from typing import TYPE_CHECKING

from app.domain.chinese import normalize_chinese_text
from app.domain.semantic_memory import MAX_ENTITY_TEXT, NormalizedEntityText

if TYPE_CHECKING:
    from .semantic_memory_metrics import SemanticMemoryMetrics


class EntityNormalizer:
    """Derive bounded comparison keys while retaining the original utterance."""

    def __init__(
        self,
        *,
        max_length: int = MAX_ENTITY_TEXT,
        metrics: "SemanticMemoryMetrics | None" = None,
    ) -> None:
        self.max_length = max(1, min(int(max_length), MAX_ENTITY_TEXT))
        self.metrics = metrics

    def normalize(self, value: str) -> NormalizedEntityText:
        started = time.perf_counter()
        try:
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
        finally:
            if self.metrics is not None:
                self.metrics.observe_ms("normalization_ms", (time.perf_counter() - started) * 1000)
