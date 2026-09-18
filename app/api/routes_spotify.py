"""Local-only Spotify authorization/status routes; tokens never leave the agent."""

from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from app.infrastructure.auth import require_api_key
from app.infrastructure.spotify_auth import SpotifyAuthError

router = APIRouter(prefix="/spotify")


@router.get("/status")
async def spotify_status(request: Request, _=Depends(require_api_key)):
    return {"success": True, "status": "ok", "data": request.app.state.runtime.spotify_auth.safe_status()}


@router.get("/auth/start")
async def spotify_auth_start(request: Request, _=Depends(require_api_key)):
    try:
        authorization_url, _state = request.app.state.runtime.spotify_auth.begin_authorization()
    except SpotifyAuthError as exc:
        return {"success": False, "status": "error", "message": str(exc), "error_code": exc.error_code}
    return {"success": True, "status": "ok", "authorization_url": authorization_url}


@router.get("/callback", response_class=PlainTextResponse)
async def spotify_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    client_host = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            return PlainTextResponse("Spotify callback 只允許本機使用。", status_code=403)
    except ValueError:
        return PlainTextResponse("Spotify callback 只允許本機使用。", status_code=403)
    if error:
        return PlainTextResponse("Spotify 授權未完成，請關閉此視窗並重新開始。", status_code=400)
    if not code or not state:
        return PlainTextResponse("Spotify callback 缺少必要參數。", status_code=400)
    try:
        request.app.state.runtime.spotify_auth.complete_authorization(code=code, state=state)
    except SpotifyAuthError:
        return PlainTextResponse("Spotify 授權驗證失敗，請重新開始。", status_code=400)
    return PlainTextResponse("Spotify 授權完成，可以關閉這個視窗。")
