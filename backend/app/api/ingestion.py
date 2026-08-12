"""POST /api/ingest — upload, chunk, embed, and store documents."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import ProviderDep, SettingsDep, StoreDep
from app.core.errors import FileTooLarge, InvalidChunkSettings, StudioError
from app.models.schemas import ChunkSettings, IngestResponse
from app.services.pipeline import UploadedFile, ingest_documents
from app.services.vector_store import validate_collection_name

router = APIRouter(prefix="/api", tags=["ingestion"])

_READ_CHUNK = 1024 * 1024  # 1 MB


async def _read_upload(upload: UploadFile, limit_bytes: int, limit_mb: int) -> bytes:
    """Read a file, stopping as soon as it exceeds the configured limit."""
    buffer = bytearray()
    while True:
        piece = await upload.read(_READ_CHUNK)
        if not piece:
            break
        buffer.extend(piece)
        if len(buffer) > limit_bytes:
            raise FileTooLarge(
                f"'{upload.filename}' is larger than the {limit_mb} MB limit."
            )
    await upload.close()
    return bytes(buffer)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    settings: SettingsDep,
    store: StoreDep,
    provider: ProviderDep,
    files: list[UploadFile] = File(..., description="Documents to index"),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    collection_name: str = Form("documents"),
) -> IngestResponse:
    if not files:
        raise StudioError("Select at least one file to process.")
    if len(files) > settings.max_files_per_request:
        raise StudioError(
            f"Upload up to {settings.max_files_per_request} files at a time."
        )

    try:
        chunk_settings = ChunkSettings(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    except ValueError as exc:
        raise InvalidChunkSettings(_first_message(exc)) from exc

    collection = validate_collection_name(collection_name)

    uploads = [
        UploadedFile(
            filename=upload.filename or "untitled",
            content_type=upload.content_type,
            data=await _read_upload(
                upload, settings.max_file_size_bytes, settings.max_file_size_mb
            ),
        )
        for upload in files
    ]

    # Extraction and embedding are CPU-bound: keep them off the event loop.
    return await run_in_threadpool(
        ingest_documents,
        uploads,
        chunk_settings,
        collection,
        store=store,
        provider=provider,
        settings=settings,
    )


def _first_message(exc: ValueError) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            detail = errors()[0]
            return str(detail.get("msg", "")).removeprefix("Value error, ") or str(exc)
        except (IndexError, KeyError, TypeError):
            pass
    return "The chunk settings are not valid."
