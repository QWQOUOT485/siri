from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request

from app.api.schemas import ActionRequest, response_payload
from app.infrastructure.auth import require_api_key
from app.infrastructure.logging import audit_event

router = APIRouter()


@router.post("/action")
async def action(request: Request, body: ActionRequest, _=Depends(require_api_key)):
    started = time.perf_counter()
    result = request.app.state.runtime.command_service.execute(body.to_validated())
    target = body.app_name or body.app_id or body.website_name or body.website_id or body.track or body.artist
    audit_event(request.app.state.runtime.logger, client_ip=request.client.host if request.client else None, action=result.action, target=target, success=result.success, duration_ms=(time.perf_counter() - started) * 1000, error_code=result.error_code)
    return response_payload(result)
