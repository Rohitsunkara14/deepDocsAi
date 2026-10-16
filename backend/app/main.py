from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.errors import IndexingError, LLMError
from app.api.ask import router as ask_router
from app.api.ready import router as ready_router
from app.core.observability import RequestLoggingMiddleware
from app.rag.llm import LLM, OpenAICompatibleLLM
from app.api.search import router as search_router
from app.services.indexing import IndexingResources, create_resources
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.body_limit import RequestBodyLimitMiddleware

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.core.config import Settings


def create_app(settings: Settings | None = None, resources: IndexingResources | None = None,
               llm: LLM | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.indexing = resources if resources is not None else create_resources(config)
        application.state.indexing.settings = config
        application.state.indexing.retriever.settings = config
        async with httpx.AsyncClient(follow_redirects=False) as client:
            application.state.llm = llm if llm is not None else OpenAICompatibleLLM(config, client)
            application.state.initialized = True
            try:
                yield
            finally:
                application.state.initialized = False
                await run_in_threadpool(application.state.indexing.close)

    application = FastAPI(title=config.app_name, debug=config.debug, lifespan=lifespan)

    @application.exception_handler(IndexingError)
    async def indexing_error_handler(request: Request, exc: IndexingError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @application.exception_handler(LLMError)
    async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    application.state.settings = config
    application.state.initialized = False
    # Bound multipart spooling too, with 64 KiB reserved for multipart overhead.
    application.add_middleware(RequestBodyLimitMiddleware,
                              max_body_size=config.max_upload_size_mb * 1024 * 1024 + 65536)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(RequestLoggingMiddleware, strategy=config.retrieval_strategy, origins=config.cors_origins)
    application.include_router(ready_router)
    application.include_router(health_router)
    application.include_router(documents_router)
    application.include_router(search_router)
    application.include_router(ask_router)
    return application


app = create_app()
