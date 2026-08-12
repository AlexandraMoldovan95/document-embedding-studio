"""Test wiring.

Each test module gets its own temporary Chroma directory, and embeddings come
from the deterministic hashing provider so the suite runs offline in seconds.
Everything else — FastAPI, the pipeline, ChromaDB itself — is the real thing.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.services.embeddings import HashingEmbeddingProvider, get_embedding_provider
from app.services.vector_store import VectorStore, get_vector_store


@pytest.fixture
def chroma_dir(tmp_path: Path) -> Path:
    path = tmp_path / "chroma"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def settings(chroma_dir: Path) -> Settings:
    return Settings(
        chroma_dir=chroma_dir,
        embedding_provider="hashing",
        embedding_model="hashing-384",
        embedding_batch_size=8,
        max_file_size_mb=5,
    )


@pytest.fixture
def store(chroma_dir: Path) -> VectorStore:
    return VectorStore(chroma_dir)


@pytest.fixture
def provider() -> HashingEmbeddingProvider:
    return HashingEmbeddingProvider()


@pytest.fixture
def client(
    settings: Settings, store: VectorStore, provider: HashingEmbeddingProvider
) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
