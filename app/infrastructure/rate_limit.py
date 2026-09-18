"""Small in-memory per-client rate limiter middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimiter:
    def __init__(self, limit: int = 120, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            if len(self._events) > 2048:
                stale_keys = [name for name, values in self._events.items() if not values or values[-1] <= cutoff]
                for name in stale_keys:
                    self._events.pop(name, None)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int = 120) -> None:
        super().__init__(app)
        self.limiter = RateLimiter(limit=limit)

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        if not self.limiter.allow(client):
            return JSONResponse(
                status_code=429,
                content={"success": False, "status": "error", "error_code": "RATE_LIMITED", "message": "Too many requests"},
            )
        return await call_next(request)
