"""Persistent ChromaDB storage.

Vectors are computed by our own :class:`EmbeddingProvider` and handed to Chroma
already built, so Chroma never downloads or runs an embedding model of its own.
Collections use cosine distance, which matches the normalised vectors the
default provider produces.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import (
    CollectionAlreadyExists,
    CollectionNotFound,
    InvalidCollectionName,
    VectorStoreError,
)

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,61}[a-zA-Z0-9]$")
_IPV4_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

MetadataValue = str | int | float | bool


@dataclass(slots=True)
class StoredChunk:
    id: str
    text: str
    metadata: dict[str, Any]
    distance: float


def validate_collection_name(name: str) -> str:
    """Apply Chroma's naming rules with messages a user can act on."""
    name = (name or "").strip()
    if not name:
        raise InvalidCollectionName("Enter a collection name.")
    if len(name) < 3 or len(name) > 63:
        raise InvalidCollectionName("Collection names must be 3 to 63 characters long.")
    if not _NAME_PATTERN.match(name):
        raise InvalidCollectionName(
            "Use letters, numbers, dots, dashes, and underscores. "
            "Start and end with a letter or number."
        )
    if ".." in name:
        raise InvalidCollectionName("Collection names cannot contain two dots in a row.")
    if _IPV4_PATTERN.match(name):
        raise InvalidCollectionName("Collection names cannot look like an IP address.")
    return name


class VectorStore:
    """Thin, typed facade over a persistent Chroma client."""

    def __init__(self, persist_directory: Path) -> None:
        self.persist_directory = persist_directory
        self._client: Any = None
        self._lock = threading.Lock()

    # -- client -----------------------------------------------------------
    def _get_client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    try:
                        import chromadb
                        from chromadb.config import Settings as ChromaSettings

                        self.persist_directory.mkdir(parents=True, exist_ok=True)
                        self._client = chromadb.PersistentClient(
                            path=str(self.persist_directory),
                            settings=ChromaSettings(
                                anonymized_telemetry=False, allow_reset=False
                            ),
                        )
                    except Exception as exc:
                        raise VectorStoreError(
                            "The vector database could not be opened. "
                            "Check that the storage directory is writable."
                        ) from exc
        return self._client

    # -- collections ------------------------------------------------------
    def list_collection_names(self) -> list[str]:
        client = self._get_client()
        try:
            collections = client.list_collections()
        except Exception as exc:
            raise VectorStoreError("Collections could not be listed.") from exc
        names = [c if isinstance(c, str) else getattr(c, "name", str(c)) for c in collections]
        return sorted(names)

    def _open(self, name: str, create: bool) -> Any:
        client = self._get_client()
        try:
            if create:
                return client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                    embedding_function=None,
                )
            return client.get_collection(name=name, embedding_function=None)
        except CollectionNotFound:
            raise
        except Exception as exc:
            if not create:
                raise CollectionNotFound(f"Collection '{name}' does not exist.") from exc
            raise VectorStoreError(f"Collection '{name}' could not be opened.") from exc

    def create_collection(self, name: str) -> str:
        name = validate_collection_name(name)
        if name in self.list_collection_names():
            raise CollectionAlreadyExists(f"A collection named '{name}' already exists.")
        self._open(name, create=True)
        return name

    def ensure_collection(self, name: str) -> str:
        name = validate_collection_name(name)
        self._open(name, create=True)
        return name

    def delete_collection(self, name: str) -> None:
        name = validate_collection_name(name)
        if name not in self.list_collection_names():
            raise CollectionNotFound(f"Collection '{name}' does not exist.")
        try:
            self._get_client().delete_collection(name=name)
        except Exception as exc:
            raise VectorStoreError(f"Collection '{name}' could not be deleted.") from exc

    def count(self, name: str) -> int:
        collection = self._open(validate_collection_name(name), create=False)
        try:
            return int(collection.count())
        except Exception as exc:
            raise VectorStoreError(f"Collection '{name}' could not be read.") from exc

    def stats(self, name: str) -> dict[str, Any]:
        """Chunk count plus the distinct documents behind it."""
        name = validate_collection_name(name)
        collection = self._open(name, create=False)
        try:
            total = int(collection.count())
            filenames: set[str] = set()
            document_ids: set[str] = set()
            offset = 0
            page = 1000
            while offset < total:
                batch = collection.get(
                    include=["metadatas"], limit=page, offset=offset
                )
                for metadata in batch.get("metadatas") or []:
                    if not metadata:
                        continue
                    if metadata.get("filename"):
                        filenames.add(str(metadata["filename"]))
                    if metadata.get("document_id"):
                        document_ids.add(str(metadata["document_id"]))
                offset += page
        except Exception as exc:
            raise VectorStoreError(f"Collection '{name}' could not be read.") from exc
        return {
            "name": name,
            "chunk_count": total,
            "document_count": len(document_ids),
            "filenames": sorted(filenames),
        }

    # -- writes -----------------------------------------------------------
    def add_chunks(
        self,
        collection_name: str,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, MetadataValue]],
        batch_size: int = 256,
    ) -> int:
        """Upsert chunks. Re-ingesting the same document replaces its chunks."""
        if not ids:
            return 0
        collection = self._open(validate_collection_name(collection_name), create=True)
        written = 0
        try:
            for start in range(0, len(ids), batch_size):
                stop = start + batch_size
                collection.upsert(
                    ids=ids[start:stop],
                    documents=texts[start:stop],
                    embeddings=embeddings[start:stop],
                    metadatas=metadatas[start:stop],
                )
                written += len(ids[start:stop])
        except Exception as exc:
            raise VectorStoreError(
                "The chunks could not be saved to the vector database."
            ) from exc
        return written

    # -- reads ------------------------------------------------------------
    def query(
        self,
        collection_name: str,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[StoredChunk]:
        collection = self._open(validate_collection_name(collection_name), create=False)
        try:
            available = int(collection.count())
            if available == 0:
                return []
            response = collection.query(
                query_embeddings=[embedding],
                n_results=min(top_k, available),
                where=where or None,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError("The search could not be completed.") from exc

        ids = (response.get("ids") or [[]])[0]
        documents = (response.get("documents") or [[]])[0]
        metadatas = (response.get("metadatas") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]

        return [
            StoredChunk(
                id=str(ids[i]),
                text=documents[i] or "",
                metadata=dict(metadatas[i] or {}),
                distance=float(distances[i]),
            )
            for i in range(len(ids))
        ]

    def peek_chunks(
        self, collection_name: str, limit: int = 50, offset: int = 0
    ) -> list[StoredChunk]:
        collection = self._open(validate_collection_name(collection_name), create=False)
        try:
            batch = collection.get(
                include=["documents", "metadatas"], limit=limit, offset=offset
            )
        except Exception as exc:
            raise VectorStoreError(f"Collection '{collection_name}' could not be read.") from exc
        ids = batch.get("ids") or []
        documents = batch.get("documents") or []
        metadatas = batch.get("metadatas") or []
        return [
            StoredChunk(
                id=str(ids[i]),
                text=(documents[i] if i < len(documents) else "") or "",
                metadata=dict((metadatas[i] if i < len(metadatas) else {}) or {}),
                distance=0.0,
            )
            for i in range(len(ids))
        ]


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(get_settings().chroma_dir)
