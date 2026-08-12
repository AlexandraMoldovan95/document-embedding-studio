"""Domain errors.

Every error raised by a service carries a short machine code and a message that
is safe to show a user. Nothing here should ever contain a stack trace, a server
path, or a library-internal string.
"""

from __future__ import annotations


class StudioError(Exception):
    """Base class for errors that are safe to surface to the client."""

    code = "error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileType(StudioError):
    code = "unsupported_file_type"
    status_code = 415


class FileTooLarge(StudioError):
    code = "file_too_large"
    status_code = 413


class EmptyDocument(StudioError):
    code = "empty_document"


class ExtractionError(StudioError):
    code = "extraction_failed"


class EncryptedDocument(StudioError):
    code = "encrypted_document"


class InvalidChunkSettings(StudioError):
    code = "invalid_chunk_settings"
    status_code = 422


class InvalidCollectionName(StudioError):
    code = "invalid_collection_name"
    status_code = 422


class CollectionNotFound(StudioError):
    code = "collection_not_found"
    status_code = 404


class CollectionAlreadyExists(StudioError):
    code = "collection_exists"
    status_code = 409


class VectorStoreError(StudioError):
    code = "vector_store_error"
    status_code = 500


class EmbeddingError(StudioError):
    code = "embedding_error"
    status_code = 500


class MissingApiKey(StudioError):
    code = "missing_api_key"
    status_code = 401


class InvalidApiKey(StudioError):
    code = "invalid_api_key"
    status_code = 401


class LLMProviderError(StudioError):
    """The upstream AI provider rejected the request or failed to respond."""

    code = "llm_provider_error"
    status_code = 502


class NoResultsFound(StudioError):
    code = "no_results_found"
    status_code = 404
