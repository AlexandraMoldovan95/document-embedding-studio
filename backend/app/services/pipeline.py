"""The ingestion pipeline.

    validate → extract → clean → chunk → build metadata → embed → store → report

Each arrow is its own function. ``ingest_documents`` only wires them together,
so a step can be swapped, tested, or moved onto a background worker without
touching the others.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import Settings
from app.core.errors import StudioError, UnsupportedFileType
from app.models.schemas import ChunkPreview, ChunkSettings, FileError, FileResult, IngestResponse
from app.services.chunking import chunk_document
from app.services.document_loader import (
    ExtractedDocument,
    get_extension,
    load_document,
    validate_content_type,
)
from app.services.embeddings import EmbeddingProvider
from app.services.vector_store import MetadataValue, VectorStore

logger = logging.getLogger(__name__)

MAX_PREVIEW_CHUNKS = 200


@dataclass(slots=True)
class UploadedFile:
    """A file as received, already read into memory."""

    filename: str
    content_type: str | None
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(slots=True)
class PreparedChunk:
    """A chunk with its stable ID and metadata, ready to be embedded."""

    id: str
    text: str
    metadata: dict[str, MetadataValue] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Step 1 — validate
# ---------------------------------------------------------------------------
def validate_upload(upload: UploadedFile, settings: Settings) -> None:
    """Check extension, declared MIME type, and size before reading further."""
    extension = get_extension(upload.filename)
    if not extension:
        raise UnsupportedFileType("This file has no extension, so its format is unknown.")
    validate_content_type(extension, upload.content_type)
    if upload.size == 0:
        raise StudioError("This file is empty.")
    if upload.size > settings.max_file_size_bytes:
        size_mb = upload.size / (1024 * 1024)
        raise StudioError(
            f"This file is {size_mb:.1f} MB. The limit is {settings.max_file_size_mb} MB."
        )


# ---------------------------------------------------------------------------
# Step 2 — extract + clean (clean_text runs inside every loader)
# ---------------------------------------------------------------------------
def extract_document(upload: UploadedFile) -> ExtractedDocument:
    return load_document(upload.filename, upload.data)


# ---------------------------------------------------------------------------
# Step 3 + 4 — chunk and attach metadata
# ---------------------------------------------------------------------------
def build_chunks(
    document: ExtractedDocument,
    settings: ChunkSettings,
    document_id: str | None = None,
) -> list[PreparedChunk]:
    """Chunk each segment separately so page numbers survive into metadata."""
    document_id = document_id or str(uuid.uuid4())
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prepared: list[PreparedChunk] = []
    chunk_index = 0

    for segment in document.segments:
        for piece in chunk_document(
            segment.text, settings.chunk_size, settings.chunk_overlap
        ):
            metadata: dict[str, MetadataValue] = {
                "document_id": document_id,
                "filename": document.filename,
                "file_type": document.file_type,
                "chunk_index": chunk_index,
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "char_count": piece.size,
                "start_char": piece.start,
                "end_char": piece.end,
                "ingested_at": ingested_at,
            }
            if segment.page is not None:
                metadata["page"] = segment.page  # Chroma rejects null metadata values
            prepared.append(
                PreparedChunk(
                    id=f"{document_id}_chunk_{chunk_index}",
                    text=piece.text,
                    metadata=metadata,
                )
            )
            chunk_index += 1

    return prepared


# ---------------------------------------------------------------------------
# Step 5 — embed
# ---------------------------------------------------------------------------
def embed_chunks(
    chunks: Sequence[PreparedChunk],
    provider: EmbeddingProvider,
    batch_size: int,
) -> list[list[float]]:
    return provider.embed_in_batches([c.text for c in chunks], batch_size)


# ---------------------------------------------------------------------------
# Step 6 — store
# ---------------------------------------------------------------------------
def store_chunks(
    store: VectorStore,
    collection_name: str,
    chunks: Sequence[PreparedChunk],
    embeddings: Sequence[list[float]],
) -> int:
    return store.add_chunks(
        collection_name=collection_name,
        ids=[c.id for c in chunks],
        texts=[c.text for c in chunks],
        embeddings=list(embeddings),
        metadatas=[c.metadata for c in chunks],
    )


def _to_preview(chunk: PreparedChunk) -> ChunkPreview:
    metadata = chunk.metadata
    page = metadata.get("page")
    return ChunkPreview(
        id=chunk.id,
        chunk_index=int(metadata.get("chunk_index", 0)),
        filename=str(metadata.get("filename", "")),
        file_type=str(metadata.get("file_type", "")),
        page=int(page) if isinstance(page, int) else None,
        char_count=len(chunk.text),
        text=chunk.text,
    )


# ---------------------------------------------------------------------------
# Orchestration — step 7, report
# ---------------------------------------------------------------------------
def ingest_documents(
    uploads: Sequence[UploadedFile],
    chunk_settings: ChunkSettings,
    collection_name: str,
    *,
    store: VectorStore,
    provider: EmbeddingProvider,
    settings: Settings,
) -> IngestResponse:
    """Run every uploaded file through the pipeline.

    A file that fails is recorded and skipped; the rest still get indexed.
    """
    started = time.perf_counter()
    collection_name = store.ensure_collection(collection_name)

    results: list[FileResult] = []
    errors: list[FileError] = []
    previews: list[ChunkPreview] = []
    seen_signatures: set[tuple[str, int]] = set()

    total_chars = 0
    total_chunks = 0
    total_embeddings = 0
    succeeded = 0

    for upload in uploads:
        extension = get_extension(upload.filename)
        signature = (upload.filename.lower(), upload.size)

        try:
            if signature in seen_signatures:
                raise StudioError("This file was uploaded twice in the same request.")
            seen_signatures.add(signature)

            validate_upload(upload, settings)
            document = extract_document(upload)

            document_id = str(uuid.uuid4())
            chunks = build_chunks(document, chunk_settings, document_id)
            if not chunks:
                raise StudioError("No text remained after chunking this document.")

            embeddings = embed_chunks(chunks, provider, settings.embedding_batch_size)
            stored = store_chunks(store, collection_name, chunks, embeddings)

            total_chars += document.char_count
            total_chunks += len(chunks)
            total_embeddings += len(embeddings)
            succeeded += 1

            for chunk in chunks:
                if len(previews) < MAX_PREVIEW_CHUNKS:
                    previews.append(_to_preview(chunk))

            results.append(
                FileResult(
                    filename=document.filename,
                    file_type=document.file_type,
                    status="indexed",
                    document_id=document_id,
                    characters=document.char_count,
                    pages=document.page_count,
                    chunks_created=len(chunks),
                    embeddings_created=stored,
                )
            )

        except StudioError as exc:
            errors.append(
                FileError(filename=upload.filename, code=exc.code, message=exc.message)
            )
            results.append(
                FileResult(
                    filename=upload.filename,
                    file_type=extension,
                    status="error",
                    error=exc.message,
                    error_code=exc.code,
                )
            )
        except Exception:  # unexpected: log internally, return something safe
            logger.exception("Unexpected failure while ingesting %s", upload.filename)
            message = "This file could not be processed."
            errors.append(
                FileError(filename=upload.filename, code="processing_failed", message=message)
            )
            results.append(
                FileResult(
                    filename=upload.filename,
                    file_type=extension,
                    status="error",
                    error=message,
                    error_code="processing_failed",
                )
            )

    duration = time.perf_counter() - started

    return IngestResponse(
        success=succeeded > 0,
        collection=collection_name,
        documents_processed=succeeded,
        documents_failed=len(errors),
        characters_extracted=total_chars,
        chunks_created=total_chunks,
        embeddings_created=total_embeddings,
        duration_seconds=round(duration, 3),
        embedding_model=provider.model_name,
        files=results,
        chunks=previews,
        errors=errors,
    )
