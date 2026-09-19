"""Bounded, aggregate-only metrics for semantic recovery."""

from __future__ import annotations

import math
import threading


COUNTER_NAMES = frozenset(
    {
        "semantic_memory_exact_hit",
        "semantic_memory_fuzzy_candidate",
        "semantic_memory_conflict",
        "semantic_memory_confirmed_write",
        "semantic_memory_provisional_write",
        "recovery_clarification",
    }
)
TIMING_NAMES = frozenset(
    {
        "normalization_ms",
        "alias_lookup_ms",
        "fuzzy_ms",
        "total_command_ms",
    }
)
_MAX_COUNTER = 1_000_000_000
_MAX_TIMING_MS = 60_000.0


class SemanticMemoryMetrics:
    """In-process counters with no labels and no raw text payloads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters = {name: 0 for name in COUNTER_NAMES}
        self._timings = {name: {"count": 0, "total_ms": 0.0, "max_ms": 0.0} for name in TIMING_NAMES}

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in COUNTER_NAMES:
            return
        try:
            value = int(amount)
        except (TypeError, ValueError):
            return
        if value <= 0:
            return
        with self._lock:
            self._counters[name] = min(_MAX_COUNTER, self._counters[name] + value)

    def observe_ms(self, name: str, duration_ms: float) -> None:
        if name not in TIMING_NAMES:
            return
        try:
            value = float(duration_ms)
        except (TypeError, ValueError):
            return
        if not math.isfinite(value) or value < 0:
            return
        value = min(_MAX_TIMING_MS, value)
        with self._lock:
            timing = self._timings[name]
            timing["count"] = min(_MAX_COUNTER, timing["count"] + 1)
            timing["total_ms"] = min(_MAX_COUNTER * _MAX_TIMING_MS, timing["total_ms"] + value)
            timing["max_ms"] = max(timing["max_ms"], value)

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "timings": {name: dict(values) for name, values in self._timings.items()},
            }
