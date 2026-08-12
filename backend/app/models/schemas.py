"""Pydantic schemas for every request and response the API exposes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

FileStatus = Literal["indexed", "error", "skipped"]


class ErrorResponse(BaseModel):
    """Uniform error envelope. Never contains server internals."""

    success: Literal[False] = False
    code: str = Field(examples=["invalid_chunk_settings"])
    message: str = Field(examples=["Chunk overlap must be smaller than chunk size."])


class ChunkSettings(BaseModel):
    """Chunking parameters, validated identically on both sides of the wire."""

    chunk_size: int = Field(default=1000, ge=100, le=10_000)
    chunk_overlap: int = Field(default=200, ge=0, le=2_000)

    @model_validator(mode="after")
    def _overlap_below_size(self) -> "ChunkSettings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"Chunk overlap must be smaller than chunk size "
                f"(got overlap={self.chunk_overlap}, chunk size={self.chunk_size})."
            )
        return self


class ChunkPreview(BaseModel):
    """A single chunk as shown in the preview panel."""

    id: str
    chunk_index: int
    filename: str
    file_type: str
    page: int | None = None
    char_count: int
    text: str


class FileError(BaseModel):
    filename: str
    code: str
    message: str


class FileResult(BaseModel):
    filename: str
    file_type: str
    status: FileStatus
    document_id: str | None = None
    characters: int = 0
    pages: int | None = None
    chunks_created: int = 0
    embeddings_created: int = 0
    error: str | None = None
    error_code: str | None = None


class IngestResponse(BaseModel):
    success: bool
    collection: str
    documents_processed: int
    documents_failed: int = 0
    characters_extracted: int = 0
    chunks_created: int
    embeddings_created: int
    duration_seconds: float = 0.0
    embedding_model: str = ""
    files: list[FileResult] = Field(default_factory=list)
    chunks: list[ChunkPreview] = Field(default_factory=list)
    errors: list[FileError] = Field(default_factory=list)


class CollectionInfo(BaseModel):
    name: str
    chunk_count: int


class CollectionListResponse(BaseModel):
    collections: list[CollectionInfo]
    default_collection: str


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=63, examples=["documents"])


class CollectionStatsResponse(BaseModel):
    name: str
    chunk_count: int
    document_count: int
    filenames: list[str] = Field(default_factory=list)


class DeleteCollectionResponse(BaseModel):
    success: Literal[True] = True
    name: str
    chunks_removed: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    collection_name: str = Field(default="documents", min_length=3, max_length=63)
    top_k: int = Field(default=5, ge=1, le=50)
    filename: str | None = Field(default=None, max_length=200)


class SearchResult(BaseModel):
    rank: int
    id: str
    score: float = Field(description="Cosine similarity, 0 to 1. Higher is closer.")
    distance: float
    filename: str
    file_type: str = ""
    page: int | None = None
    chunk_index: int | None = None
    text: str


class SearchResponse(BaseModel):
    success: bool = True
    query: str
    collection: str
    took_ms: float
    results: list[SearchResult] = Field(default_factory=list)


class ChunkListResponse(BaseModel):
    collection: str
    total: int
    chunks: list[ChunkPreview] = Field(default_factory=list)


LLMProviderName = Literal["openai", "anthropic", "gemini"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatRequest(BaseModel):
    """BYOK: the API key travels with the request and is never persisted."""

    query: str = Field(min_length=1, max_length=2_000)
    collection_name: str = Field(default="documents", min_length=3, max_length=63)
    top_k: int = Field(default=5, ge=1, le=20)
    provider: LLMProviderName
    api_key: str = Field(min_length=1, max_length=500)
    model: str | None = Field(default=None, max_length=100)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatSource(BaseModel):
    filename: str
    page: int | None = None
    chunk_index: int | None = None
    score: float
    text: str


class ChatResponse(BaseModel):
    success: bool = True
    answer: str
    provider: LLMProviderName
    model: str
    sources: list[ChatSource] = Field(default_factory=list)
    took_ms: float


class ConfigResponse(BaseModel):
    """Limits the UI mirrors so client and server never disagree."""

    default_collection: str
    embedding_model: str
    embedding_provider: str
    supported_extensions: list[str]
    max_file_size_mb: int
    max_files_per_request: int
    min_chunk_size: int
    max_chunk_size: int
    max_overlap: int
    default_chunk_size: int = 1000
    default_chunk_overlap: int = 200
