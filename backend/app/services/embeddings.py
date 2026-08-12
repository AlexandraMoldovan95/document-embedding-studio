"""Embedding providers.

The pipeline only ever talks to :class:`EmbeddingProvider`. Adding OpenAI (or
any other backend) means writing one more subclass and registering it in
:func:`build_provider` — nothing in ingestion, chunking, or storage changes.
"""

from __future__ import annotations

import hashlib
import math
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.errors import EmbeddingError

ProgressCallback = Callable[[int, int], None]


class EmbeddingProvider(ABC):
    """Turns text into vectors."""

    name: str = "provider"
    model_name: str = "unknown"

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of chunk texts."""

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector length produced by this provider."""

    def warm_up(self) -> None:
        """Optionally pre-load weights so the first request is not slow."""

    def embed_in_batches(
        self,
        texts: Sequence[str],
        batch_size: int,
        on_progress: ProgressCallback | None = None,
    ) -> list[list[float]]:
        """Embed many texts in fixed-size batches, reporting progress."""
        if not texts:
            return []
        batch_size = max(1, batch_size)
        vectors: list[list[float]] = []
        total = len(texts)
        for start in range(0, total, batch_size):
            batch = list(texts[start : start + batch_size])
            vectors.extend(self.embed_documents(batch))
            if on_progress is not None:
                on_progress(min(start + batch_size, total), total)
        return vectors


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local, free, no API key. Weights load lazily on first use."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:  # pragma: no cover
                        raise EmbeddingError(
                            "The embedding library is not installed on this server."
                        ) from exc
                    try:
                        self._model = SentenceTransformer(self.model_name)
                    except Exception as exc:
                        raise EmbeddingError(
                            f"The embedding model '{self.model_name}' could not be loaded. "
                            "Check the model name and that the machine can reach the "
                            "model cache."
                        ) from exc
        return self._model

    def warm_up(self) -> None:
        self._load()

    @property
    def dimension(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        try:
            vectors = model.encode(
                texts,
                batch_size=len(texts),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError("Embeddings could not be generated for this batch.") from exc
        return [[float(value) for value in row] for row in vectors]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_documents([query])[0]


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashing embeddings — no model download, no network.

    This exists so the test suite and CI can exercise the full ingest → store →
    search path in seconds. It is a real (if crude) bag-of-words vector space,
    not a stub: identical text always yields identical vectors and shared
    vocabulary raises cosine similarity. It is never the default.
    """

    name = "hashing"

    def __init__(self, dimension: int = 384) -> None:
        self.model_name = f"hashing-{dimension}"
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in self._tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokens(text: str) -> Iterable[str]:
        return (token for token in text.lower().split() if token)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._vector(query)


def build_provider(settings: Settings) -> EmbeddingProvider:
    """Map configuration to a provider instance."""
    provider = settings.embedding_provider.strip().lower()
    if provider in {"sentence-transformers", "sentence_transformers", "local"}:
        return SentenceTransformerEmbeddingProvider(settings.embedding_model)
    if provider in {"hashing", "hash-test"}:
        return HashingEmbeddingProvider()
    # A future OpenAIEmbeddingProvider would be registered here.
    raise EmbeddingError(f"Unknown embedding provider '{settings.embedding_provider}'.")


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Process-wide singleton: model weights are loaded at most once."""
    return build_provider(get_settings())
