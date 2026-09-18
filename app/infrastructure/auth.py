"""API-key authentication with constant-time comparison and safe errors."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status

from .config import AppConfig
from .rate_limit import RateLimiter


def verify_api_key(provided: str | None, configured: str) -> bool:
    if not provided or not configured:
        return False
    return secrets.compare_digest(provided.encode("utf-8"), configured.encode("utf-8"))


def api_key_dependency(config: AppConfig):
    async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if not verify_api_key(x_api_key, config.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "AUTH_FAILED", "message": "Authentication failed"},
            )

    return require_api_key


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that reads the request app's configured key."""

    config: AppConfig = request.app.state.runtime.config
    if not verify_api_key(x_api_key, config.api_key):
        limiter = getattr(request.app.state, "auth_fail_limiter", None)
        client = request.client.host if request.client else "unknown"
        if limiter is not None and not limiter.allow(client):
            raise HTTPException(status_code=429, detail={"error_code": "AUTH_RATE_LIMITED", "message": "Authentication temporarily limited"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "AUTH_FAILED", "message": "Authentication failed"},
        )
