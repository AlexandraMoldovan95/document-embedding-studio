"""Collection management: list, create, inspect, browse chunks, delete."""

from __future__ import annotations

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from app.api.deps import SettingsDep, StoreDep
from app.models.schemas import (
    ChunkListResponse,
    ChunkPreview,
    CollectionCreateRequest,
    CollectionInfo,
    CollectionListResponse,
    CollectionStatsResponse,
    DeleteCollectionResponse,
)

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.get("", response_model=CollectionListResponse)
async def list_collections(store: StoreDep, settings: SettingsDep) -> CollectionListResponse:
    names = await run_in_threadpool(store.list_collection_names)
    infos = [
        CollectionInfo(name=name, chunk_count=await run_in_threadpool(store.count, name))
        for name in names
    ]
    return CollectionListResponse(
        collections=infos, default_collection=settings.default_collection
    )


@router.post("", response_model=CollectionInfo, status_code=201)
async def create_collection(payload: CollectionCreateRequest, store: StoreDep) -> CollectionInfo:
    name = await run_in_threadpool(store.create_collection, payload.name)
    return CollectionInfo(name=name, chunk_count=0)


@router.get("/{name}/stats", response_model=CollectionStatsResponse)
async def collection_stats(name: str, store: StoreDep) -> CollectionStatsResponse:
    stats = await run_in_threadpool(store.stats, name)
    return CollectionStatsResponse(**stats)


@router.get("/{name}/chunks", response_model=ChunkListResponse)
async def list_chunks(
    name: str,
    store: StoreDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChunkListResponse:
    """Page through stored chunks — this is what the preview panel reads."""
    total = await run_in_threadpool(store.count, name)
    stored = await run_in_threadpool(store.peek_chunks, name, limit, offset)
    chunks = [
        ChunkPreview(
            id=item.id,
            chunk_index=int(item.metadata.get("chunk_index", index + offset)),
            filename=str(item.metadata.get("filename", "unknown")),
            file_type=str(item.metadata.get("file_type", "")),
            page=_as_int(item.metadata.get("page")),
            char_count=int(item.metadata.get("char_count", len(item.text))),
            text=item.text,
        )
        for index, item in enumerate(stored)
    ]
    return ChunkListResponse(collection=name, total=total, chunks=chunks)


@router.delete("/{name}", response_model=DeleteCollectionResponse)
async def delete_collection(name: str, store: StoreDep) -> DeleteCollectionResponse:
    removed = await run_in_threadpool(store.count, name)
    await run_in_threadpool(store.delete_collection, name)
    return DeleteCollectionResponse(name=name, chunks_removed=removed)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None
