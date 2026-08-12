"""Shared dependencies. Overriding these in tests swaps the real services out."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.vector_store import VectorStore, get_vector_store

SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[VectorStore, Depends(get_vector_store)]
ProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
