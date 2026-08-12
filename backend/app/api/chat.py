"""POST /api/chat — retrieval (Chroma) + generation (BYOK LLM), i.e. the "G" in RAG.

Retrieval reuses the exact same embedding provider and vector store as
/api/search. Generation is entirely optional to the app's core value: if this
endpoint is never called, nothing about ingestion or search changes.
"""
from __future__ import annotations

import time

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.api.deps import ProviderDep, StoreDep
from app.core.errors import NoResultsFound
from app.models.schemas import ChatRequest, ChatResponse, ChatSource
from app.services.llm_providers import generate_answer
from app.services.vector_store import validate_collection_name

router = APIRouter(prefix="/api", tags=["chat"])

_SYSTEM_PROMPT = (
    "You are a helpful assistant answering questions using ONLY the document "
    "excerpts provided below. Answer in clear, natural, human language — "
    "detailed where the source material supports it, concise where it doesn't. "
    "If the excerpts don't contain the answer, say so plainly rather than "
    "guessing or using outside knowledge. When useful, mention which source "
    "file the information came from."
)


def _similarity(distance: float) -> float:
    return round(max(0.0, min(1.0, 1.0 - distance)), 4)


def _build_user_prompt(query: str, sources: list[ChatSource]) -> str:
    if not sources:
        return f"Question: {query}\n\n(No relevant excerpts were found in the collection.)"

    blocks = []
    for i, s in enumerate(sources, start=1):
        location = f"{s.filename}" + (f", page {s.page}" if s.page else "")
        blocks.append(f"[Excerpt {i} — {location}]\n{s.text}")

    excerpts = "\n\n".join(blocks)
    return f"Document excerpts:\n\n{excerpts}\n\nQuestion: {query}"


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, store: StoreDep, provider: ProviderDep) -> ChatResponse:
    started = time.perf_counter()
    collection = validate_collection_name(payload.collection_name)
    query = payload.query.strip()

    embedding = await run_in_threadpool(provider.embed_query, query)
    matches = await run_in_threadpool(store.query, collection, embedding, payload.top_k, None)

    if not matches:
        raise NoResultsFound(
            f"No chunks are indexed yet in '{collection}'. Process some documents first."
        )

    sources = [
        ChatSource(
            filename=str(m.metadata.get("filename", "unknown")),
            page=m.metadata.get("page"),
            chunk_index=m.metadata.get("chunk_index"),
            score=_similarity(m.distance),
            text=m.text,
        )
        for m in matches
    ]

    user_prompt = _build_user_prompt(query, sources)

    answer, model_used = await generate_answer(
        provider=payload.provider,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        api_key=payload.api_key,
        model=payload.model,
    )

    return ChatResponse(
        answer=answer,
        provider=payload.provider,
        model=model_used,
        sources=sources,
        took_ms=round((time.perf_counter() - started) * 1000, 2),
    )
