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
    if body.clarification_token:
        result = runtime.command_service.execute_clarification(body.text, body.clarification_token)
        audit_event(
            runtime.logger,
            client_ip=request.client.host if request.client else None,
            action=result.action,
            target="spotify_clarification",
            success=result.success,
            duration_ms=(time.perf_counter() - started) * 1000,
            error_code=result.error_code,
        )
        return response_payload(result)

    parsed = runtime.parser.parse(body.text)
    if not parsed.accepted or parsed.action is None:
        ai_result = runtime.local_ai_service.retry(
            body.text,
            parsed,
            deterministic_error_code=parsed.error_code,
        )
        if ai_result.execution_allowed and ai_result.action is not None:
            result = runtime.command_service.execute(ai_result.action, source_text=body.text)
            target = ai_result.action.track or ai_result.action.artist or ai_result.action.album
            audit_event(
                runtime.logger,
                client_ip=request.client.host if request.client else None,
                action=result.action,
                target=target,
                success=result.success,
                duration_ms=(time.perf_counter() - started) * 1000,
                error_code=result.error_code,
            )
            return response_payload(result)
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
    result = runtime.command_service.execute(parsed.action, source_text=body.text)
    ai_result = runtime.local_ai_service.retry(
        body.text,
        parsed,
        deterministic_success=result.success,
        deterministic_error_code=result.error_code,
    )
    parsed_action = parsed.action
    if ai_result.execution_allowed and ai_result.action is not None:
        result = runtime.command_service.execute(ai_result.action, source_text=body.text)
        parsed_action = ai_result.action
    target = (
        parsed_action.app_query
        or parsed_action.app_id
        or parsed_action.website_query
        or parsed_action.website_id
        or parsed_action.track
        or parsed_action.artist
        or parsed_action.album
    )
    audit_event(runtime.logger, client_ip=request.client.host if request.client else None, action=result.action, target=target, success=result.success, duration_ms=(time.perf_counter() - started) * 1000, error_code=result.error_code)
    return response_payload(result)
