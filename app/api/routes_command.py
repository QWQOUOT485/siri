from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request

from app.api.schemas import CommandRequest, response_payload
from app.infrastructure.auth import require_api_key
from app.infrastructure.logging import audit_event

router = APIRouter()


@router.post("/command")
async def command(request: Request, body: CommandRequest, _=Depends(require_api_key)):
    runtime = request.app.state.runtime
    started = time.perf_counter()
    parsed = runtime.parser.parse(body.text)
    if not parsed.accepted or parsed.action is None:
        audit_event(runtime.logger, client_ip=request.client.host if request.client else None, action="parse_command", target=None, success=False, duration_ms=(time.perf_counter() - started) * 1000, error_code=parsed.error_code)
        return {
            "success": False,
            "status": "error",
            "action": "parse_command",
            "message": parsed.message,
            "candidates": [],
            "confirmation_required": False,
            "error_code": parsed.error_code or "INVALID_COMMAND",
            "data": {},
        }
    result = runtime.command_service.execute(parsed.action)
    target = (
        parsed.action.app_query
        or parsed.action.app_id
        or parsed.action.website_query
        or parsed.action.website_id
        or parsed.action.track
        or parsed.action.artist
    )
    audit_event(runtime.logger, client_ip=request.client.host if request.client else None, action=result.action, target=target, success=result.success, duration_ms=(time.perf_counter() - started) * 1000, error_code=result.error_code)
    return response_payload(result)
