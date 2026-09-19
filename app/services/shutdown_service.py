"""One-time, expiring shutdown confirmation tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class _TokenRecord:
    digest: bytes
    expires_at: float
    used: bool = False


class ShutdownConfirmationService:
    def __init__(self, ttl_seconds: int = 60, *, clock=time.monotonic) -> None:
        self.ttl_seconds = max(15, min(600, int(ttl_seconds)))
        self._clock = clock
        self._records: dict[bytes, _TokenRecord] = {}
        self._lock = Lock()

    def request(self) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        digest = self._digest(token)
        with self._lock:
            self._purge_locked()
            self._records[digest] = _TokenRecord(digest=digest, expires_at=self._clock() + self.ttl_seconds)
        return token, self.ttl_seconds

    def consume(self, token: str | None) -> tuple[bool, str]:
        if not token or len(token) > 512:
            return False, "SHUTDOWN_TOKEN_INVALID"
        digest = self._digest(token)
        with self._lock:
            record = self._records.get(digest)
            if record is None or not hmac.compare_digest(record.digest, digest):
                return False, "SHUTDOWN_TOKEN_INVALID"
            if record.used:
                return False, "SHUTDOWN_TOKEN_REUSED"
            if record.expires_at <= self._clock():
                self._records.pop(digest, None)
                return False, "SHUTDOWN_TOKEN_EXPIRED"
            self._purge_locked()
            record.used = True
            return True, ""

    def _purge_locked(self) -> None:
        now = self._clock()
        expired = [digest for digest, record in self._records.items() if record.expires_at <= now]
        for digest in expired:
            self._records.pop(digest, None)

    @staticmethod
    def _digest(token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()
