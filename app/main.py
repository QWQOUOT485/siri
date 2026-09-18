"""FastAPI entry point for the LAN-only Windows Siri Agent."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes_action import router as action_router
from app.api.routes_apps import router as apps_router
from app.api.routes_command import router as command_router
from app.api.routes_health import router as health_router
from app.api.routes_spotify import router as spotify_router
from app.infrastructure.network import PrivateNetworkMiddleware
from app.infrastructure.rate_limit import RateLimiter, RateLimitMiddleware
from app.runtime import AgentRuntime, build_runtime


def create_app(runtime: AgentRuntime | None = None, *, refresh_on_startup: bool | None = None, test_mode: bool = False) -> FastAPI:
    runtime = runtime or build_runtime(startup_refresh=True if refresh_on_startup is None else refresh_on_startup)
    should_refresh = runtime.startup_refresh if refresh_on_startup is None else refresh_on_startup

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if should_refresh:
            try:
                runtime.catalog.refresh()
            except Exception:
                runtime.logger.exception("startup catalog refresh failed")
        yield

    application = FastAPI(title="Windows Siri Agent", version="0.1.0", lifespan=lifespan)
    application.state.runtime = runtime
    application.state.auth_fail_limiter = RateLimiter(limit=10, window_seconds=60.0)
    application.add_middleware(RateLimitMiddleware, limit=runtime.config.rate_limit_per_minute)
    application.add_middleware(PrivateNetworkMiddleware, allowed_networks=runtime.config.allowed_networks, allow_testclient=test_mode)
    application.include_router(health_router)
    application.include_router(apps_router)
    application.include_router(action_router)
    application.include_router(command_router)
    application.include_router(spotify_router)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"success": False, "status": "error", "action": "request_validation", "message": "請求格式不正確。", "candidates": [], "confirmation_required": False, "error_code": "MALFORMED_REQUEST", "data": {}},
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger = getattr(request.app.state.runtime, "logger", logging.getLogger("siri_agent"))
        logger.exception("unhandled request error")
        return JSONResponse(
            status_code=500,
            content={"success": False, "status": "error", "action": "request", "message": "Agent 發生內部錯誤，詳細資訊已寫入本機 log。", "candidates": [], "confirmation_required": False, "error_code": "INTERNAL_ERROR", "data": {}},
        )

    return application


app = create_app()


def main() -> None:
    import uvicorn

    runtime = app.state.runtime
    uvicorn.run(app, host=runtime.config.bind_address, port=runtime.config.port, log_level=runtime.config.log_level.lower())


if __name__ == "__main__":
    main()
