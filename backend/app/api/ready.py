from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

router = APIRouter(tags=["health"])


@router.get("/ready", responses={503: {"description": "Application or collection unavailable"}})
async def ready(request: Request) -> JSONResponse:
    initialized = getattr(request.app.state, "initialized", False)
    if not initialized:
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "application_initializing"})
    try:
        await run_in_threadpool(request.app.state.indexing.store.check_ready)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "qdrant_collection_unavailable"})
    return JSONResponse(content={"status": "ready", "service": "deepdocs-ai"})
