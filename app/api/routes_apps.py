from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.schemas import SearchRequest, response_payload
from app.infrastructure.auth import require_api_key

router = APIRouter()


@router.get("/info")
async def info(request: Request, _=Depends(require_api_key)):
    return {"success": True, "status": "ok", **request.app.state.runtime.info()}


@router.get("/apps")
async def apps(request: Request, _=Depends(require_api_key)):
    runtime = request.app.state.runtime
    return {"success": True, "status": "ok", "count": len(runtime.catalog.entries()), "apps": [entry.public_view() for entry in runtime.catalog.entries()]}


@router.post("/apps/search")
async def search(request: Request, body: SearchRequest, _=Depends(require_api_key)):
    result = request.app.state.runtime.catalog.search(body.query)
    return {
        "success": True,
        "status": "ok",
        "action": "search_apps",
        "message": "搜尋完成。",
        "query": result.query,
        "best_match": result.best_match.model_dump() if result.best_match else None,
        "candidates": [candidate.model_dump() for candidate in result.candidates],
        "ambiguous": result.ambiguous,
    }


@router.post("/apps/refresh")
async def refresh(request: Request, _=Depends(require_api_key)):
    result = request.app.state.runtime.application_service.refresh()
    return response_payload(result)
