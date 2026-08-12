"""Application configuration, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Server ---
    app_name: str = "Document Embedding Studio"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # --- Storage ---
    chroma_dir: Path = Path("./data/chroma")
    default_collection: str = "documents"

    # --- Embeddings ---
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = Field(default=64, ge=1, le=1024)
    # Set to 1 to load the model eagerly at startup instead of on first use.
    embedding_warmup: bool = False

    # --- Upload limits ---
    max_file_size_mb: int = Field(default=50, ge=1, le=1024)
    max_files_per_request: int = Field(default=25, ge=1, le=200)

    # --- Chunking bounds (mirrored by the UI) ---
    min_chunk_size: int = 100
    max_chunk_size: int = 10_000
    max_overlap: int = 2_000

    @field_validator("chroma_dir", mode="after")
    @classmethod
    def _resolve(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
