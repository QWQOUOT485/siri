from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    runtime = request.app.state.runtime
    return {
        "ok": True,
        "status": "Agent online",
        "version": _version(),
        "uptime_seconds": runtime.uptime_seconds(),
    }


@router.get("/", include_in_schema=False)
async def status_page(request: Request):
    runtime = request.app.state.runtime
    return HTMLResponse(f"""<!doctype html><html lang='zh-Hant'><meta charset='utf-8'><title>Windows Siri Agent</title>
<style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:3rem auto;padding:0 1rem}}.ok{{color:#087f23}}</style>
<h1 class='ok'>Agent Online</h1><p>Windows Siri Agent 正在執行。</p>
<p>版本：{_version()}<br>已發現應用程式：{len(runtime.catalog.entries())}</p>
<p>健康檢查：<a href='/health'>/health</a>（此頁不顯示 API key）</p></html>""")


def _version() -> str:
    from app import __version__

    return __version__
