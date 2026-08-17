"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, collections, ingestion, monitor, search
from app.api.deps import SettingsDep
from app.core.config import get_settings
from app.core.errors import StudioError
from app.models.schemas import ConfigResponse, ErrorResponse
from app.services.document_loader import SUPPORTED_EXTENSIONS
from app.services.embeddings import get_embedding_provider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("studio")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Vector storage: %s", settings.chroma_dir)
    if settings.embedding_warmup:
        logger.info("Loading embedding model %s...", settings.embedding_model)
        try:
            get_embedding_provider().warm_up()
        except Exception:
            # A failed warm-up must not stop the server; the first request will
            # surface a clean error instead.
            logger.exception("Embedding model warm-up failed")
    yield


app = FastAPI(
    title="Document Embedding Studio",
    description="Chunk, embed, and store documents in ChromaDB.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(collections.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(monitor.router)


@app.exception_handler(StudioError)
async def studio_error_handler(_: Request, exc: StudioError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    detail = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in detail.get("loc", ())[1:]) or "request"
    message = str(detail.get("msg", "Invalid request.")).removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="invalid_request", message=f"{field}: {message}"
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="internal_error", message="Something went wrong on the server."
        ).model_dump(),
    )


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config", response_model=ConfigResponse, tags=["meta"])
async def config(settings: SettingsDep) -> ConfigResponse:
    """Limits and defaults the frontend mirrors, so the two never disagree."""
    return ConfigResponse(
        default_collection=settings.default_collection,
        embedding_model=settings.embedding_model,
        embedding_provider=settings.embedding_provider,
        supported_extensions=sorted(SUPPORTED_EXTENSIONS),
        max_file_size_mb=settings.max_file_size_mb,
        max_files_per_request=settings.max_files_per_request,
        min_chunk_size=settings.min_chunk_size,
        max_chunk_size=settings.max_chunk_size,
        max_overlap=settings.max_overlap,
    )
