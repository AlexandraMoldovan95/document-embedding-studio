/** Types mirroring the Pydantic schemas in `backend/app/models/schemas.py`. */

export type FileStatus =
  | "ready"
  | "uploading"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexed"
  | "error";

/** A file chosen in the browser, plus everything the UI tracks about it. */
export interface QueuedFile {
  id: string;
  file: File;
  name: string;
  extension: string;
  size: number;
  status: FileStatus;
  /** 0–100 while the bytes are being uploaded. */
  uploadProgress: number;
  chunksCreated: number;
  characters: number;
  pages: number | null;
  error: string | null;
}

export interface ChunkPreview {
  id: string;
  chunk_index: number;
  filename: string;
  file_type: string;
  page: number | null;
  char_count: number;
  text: string;
}

export interface FileError {
  filename: string;
  code: string;
  message: string;
}

export interface FileResult {
  filename: string;
  file_type: string;
  status: "indexed" | "error" | "skipped";
  document_id: string | null;
  characters: number;
  pages: number | null;
  chunks_created: number;
  embeddings_created: number;
  error: string | null;
  error_code: string | null;
}

export interface IngestResponse {
  success: boolean;
  collection: string;
  documents_processed: number;
  documents_failed: number;
  characters_extracted: number;
  chunks_created: number;
  embeddings_created: number;
  duration_seconds: number;
  embedding_model: string;
  files: FileResult[];
  chunks: ChunkPreview[];
  errors: FileError[];
}

export interface CollectionInfo {
  name: string;
  chunk_count: number;
}

export interface CollectionListResponse {
  collections: CollectionInfo[];
  default_collection: string;
}

export interface CollectionStats {
  name: string;
  chunk_count: number;
  document_count: number;
  filenames: string[];
}

export interface DeleteCollectionResponse {
  success: true;
  name: string;
  chunks_removed: number;
}

export interface SearchResult {
  rank: number;
  id: string;
  score: number;
  distance: number;
  filename: string;
  file_type: string;
  page: number | null;
  chunk_index: number | null;
  text: string;
}

export interface SearchResponse {
  success: boolean;
  query: string;
  collection: string;
  took_ms: number;
  results: SearchResult[];
}

export interface ChunkListResponse {
  collection: string;
  total: number;
  chunks: ChunkPreview[];
}

export interface StudioConfig {
  default_collection: string;
  embedding_model: string;
  embedding_provider: string;
  supported_extensions: string[];
  max_file_size_mb: number;
  max_files_per_request: number;
  min_chunk_size: number;
  max_chunk_size: number;
  max_overlap: number;
  default_chunk_size: number;
  default_chunk_overlap: number;
}

/* -------------------------------------------------------------------------- */
/* Container monitor (live, via WebSocket)                                    */
/* -------------------------------------------------------------------------- */

export interface ContainerSnapshot {
  id: string;
  name: string;
  image: string;
  status: string;
  cpu_percent: number;
  memory_used_mb: number;
  memory_limit_mb: number;
}

export interface ContainerMonitorMessage {
  ok: boolean;
  containers: ContainerSnapshot[];
  error: string | null;
}

/* -------------------------------------------------------------------------- */
/* Chat (BYOK)                                                                 */
/* -------------------------------------------------------------------------- */

export type LlmProvider = "openai" | "anthropic" | "gemini";

export const LLM_PROVIDERS: { id: LlmProvider; label: string; defaultModel: string }[] = [
  { id: "openai", label: "OpenAI", defaultModel: "gpt-4o-mini" },
  { id: "anthropic", label: "Anthropic", defaultModel: "claude-3-5-sonnet-latest" },
  { id: "gemini", label: "Google Gemini", defaultModel: "gemini-3.6-flash" },
];

export interface ChatSource {
  filename: string;
  page: number | null;
  chunk_index: number | null;
  score: number;
  text: string;
}

export interface ChatResponse {
  success: boolean;
  answer: string;
  provider: LlmProvider;
  model: string;
  sources: ChatSource[];
  took_ms: number;
}

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  error?: string;
}

/** Aggregate of the per-file ingest calls in one "Process & embed" run. */
export interface RunSummary {
  collection: string;
  documentsProcessed: number;
  documentsFailed: number;
  charactersExtracted: number;
  chunksCreated: number;
  embeddingsCreated: number;
  durationSeconds: number;
  embeddingModel: string;
  errors: FileError[];
}
