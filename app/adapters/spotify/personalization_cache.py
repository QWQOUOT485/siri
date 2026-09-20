"""Bounded, process-local cache for Spotify personalization evidence."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class _CacheEntry:
    value: Any
    expires_at: float
    stale_until: float


class SpotifyPersonalizationCache:
    """Keep short-lived server-side ranking evidence without persisting secrets."""

    DEFAULT_TTL_SECONDS = 60.0
    DEFAULT_STALE_GRACE_SECONDS = 30.0
    DEFAULT_MAX_ENTRIES = 12
    MAX_TTL_SECONDS = 3600.0
    MAX_STALE_GRACE_SECONDS = 3600.0
    MAX_ENTRIES = 32

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        stale_grace_seconds: float = DEFAULT_STALE_GRACE_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._clock = clock
        self.ttl_seconds = self._bounded_seconds(ttl_seconds, self.MAX_TTL_SECONDS)
        self.stale_grace_seconds = self._bounded_seconds(stale_grace_seconds, self.MAX_STALE_GRACE_SECONDS)
        self.max_entries = max(1, min(int(max_entries), self.MAX_ENTRIES))
        self._scope_key = secrets.token_bytes(32)
        self._entries: OrderedDict[tuple[bytes, str], _CacheEntry] = OrderedDict()
        self._lock = RLock()

    def scope_for(self, access_token: str) -> bytes:
        """Derive a process-local scope key without retaining the raw token."""

        return hmac.new(self._scope_key, access_token.encode("utf-8"), hashlib.sha256).digest()

    def get_fresh(self, scope: bytes, signal: str) -> Any | None:
        with self._lock:
            entry = self._entries.get((scope, signal))
            if entry is None or self._clock() >= entry.expires_at:
                return None
            self._entries.move_to_end((scope, signal))
            return entry.value

    def get_stale(self, scope: bytes, signal: str) -> Any | None:
        with self._lock:
            key = (scope, signal)
            entry = self._entries.get(key)
            if entry is None:
                return None
            now = self._clock()
            if now >= entry.stale_until:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry.value

    def put(self, scope: bytes, signal: str, value: Any) -> None:
        now = self._clock()
        key = (scope, signal)
        with self._lock:
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=now + self.ttl_seconds,
                stale_until=now + self.ttl_seconds + self.stale_grace_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @staticmethod
    def _bounded_seconds(value: float, maximum: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if value != value or value in {float("inf"), float("-inf")}:
            return 0.0
        return max(0.0, min(value, maximum))
