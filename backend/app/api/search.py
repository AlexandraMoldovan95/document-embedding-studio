"""POST /api/search — embed the query, then ask Chroma for the nearest chunks."""

from __future__ import annotations

import time

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.api.deps import ProviderDep, StoreDep
from app.models.schemas import SearchRequest, SearchResponse, SearchResult
from app.services.vector_store import validate_collection_name

router = APIRouter(prefix="/api", tags=["search"])


def _similarity(distance: float) -> float:
    """Cosine distance to a 0–1 similarity score, clamped for display."""
    return round(max(0.0, min(1.0, 1.0 - distance)), 4)


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest, store: StoreDep, provider: ProviderDep
) -> SearchResponse:
    collection = validate_collection_name(payload.collection_name)
    query = payload.query.strip()
    started = time.perf_counter()

    embedding = await run_in_threadpool(provider.embed_query, query)
    where = {"filename": payload.filename} if payload.filename else None
    matches = await run_in_threadpool(
        store.query, collection, embedding, payload.top_k, where
    )

    results = [
        SearchResult(
            rank=index + 1,
            id=match.id,
            score=_similarity(match.distance),
            distance=round(match.distance, 4),
            filename=str(match.metadata.get("filename", "unknown")),
            file_type=str(match.metadata.get("file_type", "")),
            page=_as_int(match.metadata.get("page")),
            chunk_index=_as_int(match.metadata.get("chunk_index")),
            text=match.text,
        )
        for index, match in enumerate(matches)
    ]

    return SearchResponse(
        query=query,
        collection=collection,
        took_ms=round((time.perf_counter() - started) * 1000, 2),
        results=results,
    )


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None
