# Document Embedding Studio

A local-first web application for building the ingestion side of a RAG system. Drop in PDF, DOCX, Markdown, or plain-text files, choose a chunk size and overlap, and the app extracts the text, splits it into chunks, embeds every chunk with a local sentence-transformers model, and stores vectors, text, and metadata in a persistent ChromaDB collection. A built-in search tester lets you query what you just indexed. No API keys, no paid services, and nothing leaves your machine.

## Architecture

The processing flow is a straight pipeline, and each arrow is its own module:

```
Upload → Validate → Extract text → Clean text → Chunk → Metadata → Embed → Store in ChromaDB → Report
```

The backend is FastAPI with a strict separation of concerns. `document_loader.py` turns file bytes into cleaned text segments (per page for PDFs). `chunking.py` splits segments into overlapping character windows. `embeddings.py` defines an `EmbeddingProvider` abstraction with a sentence-transformers implementation behind it. `vector_store.py` wraps a persistent Chroma client. `pipeline.py` composes those steps and reports per-file results, so one corrupt file never cancels the rest of a batch. The frontend is Next.js (App Router) with strict TypeScript; it mirrors the backend's validation rules, streams real upload progress, and renders chunk previews and search results.

ChromaDB runs embedded inside the backend process using `PersistentClient`, writing to `./data/chroma` by default. There is no separate database server to install or start, and collections survive restarts.

```
backend/
  app/
    main.py                 FastAPI app, error handlers, /api/health, /api/config
    api/
      ingestion.py          POST /api/ingest (multipart upload)
      collections.py        list / create / stats / chunks / delete
      search.py             POST /api/search
      deps.py               dependency wiring (overridable in tests)
    services/
      document_loader.py    PDF, DOCX, TXT, MD extraction + sanitisation
      chunking.py           character windows, overlap, boundary snapping
      embeddings.py         EmbeddingProvider + SentenceTransformer impl
      vector_store.py       persistent ChromaDB facade
      pipeline.py           orchestration of the steps above
    models/schemas.py       Pydantic request/response models
    core/config.py          settings from environment / .env
    core/errors.py          safe, typed domain errors
  tests/                    62 tests: chunking, loaders, full API
  pyproject.toml
  .env.example
  Dockerfile

frontend/
  app/                      layout, page, global styles
  components/
    FileDropzone.tsx        keyboard-accessible drag & drop
    FileList.tsx            per-file status, progress, errors
    ChunkSettings.tsx       size + overlap sliders with live validation
    CollectionSelector.tsx  select / create / delete (with confirmation)
    ProcessingStatus.tsx    progress and run statistics
    ChunkPreview.tsx        chunk cards with real overlap highlighting
    SearchTester.tsx        semantic search panel
    Primitives.tsx          buttons, alerts, icons, progress bars
  lib/                      typed API client, shared types, helpers
  package.json
  Dockerfile

docker-compose.yml
```

## Requirements

Python 3.12 or newer, Node.js 20 or newer, and roughly 3 GB of disk for the Python ML dependencies (sentence-transformers pulls in PyTorch). The embedding model itself (~90 MB) downloads automatically on first use and is cached afterwards.

## Quick start

Run the backend and frontend in two terminals.

**Terminal 1 — backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm install
cp .env.local.example .env.local     # points at http://localhost:8000 by default
npm run dev
```

Open http://localhost:3000. The very first "Process & embed" run downloads the embedding model, so it takes a minute; every run after that is fast. Interactive API docs are at http://localhost:8000/docs.

## Docker

```bash
docker compose up --build
```

This builds both images and starts the stack with the frontend on port 3000 and the backend on port 8000. Vectors persist in the `chroma-data` named volume and model weights in `hf-cache`, so both survive `docker compose down`. The compose file sets `EMBEDDING_WARMUP=true` so the model loads during startup rather than on the first request.

## Configuration

The backend reads settings from environment variables or a `.env` file — copy `backend/.env.example` to get started. Defaults are sensible, so no configuration is required for local use.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CHROMA_DIR` | `./data/chroma` | Where ChromaDB persists vectors |
| `DEFAULT_COLLECTION` | `documents` | Collection preselected in the UI |
| `EMBEDDING_PROVIDER` | `sentence-transformers` | Provider key (see below) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model name for the provider |
| `EMBEDDING_BATCH_SIZE` | `64` | Chunks embedded per batch |
| `EMBEDDING_WARMUP` | `false` | Load the model at startup |
| `MAX_FILE_SIZE_MB` | `50` | Per-file upload limit |
| `MAX_FILES_PER_REQUEST` | `25` | Files per ingest request |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |

The frontend has a single variable, `NEXT_PUBLIC_API_URL`, in `frontend/.env.local.example`.

## Supported file formats

| Format | Parser | Notes |
| --- | --- | --- |
| `.pdf` | PyMuPDF | Text is extracted per page, and every chunk keeps its source page number. Encrypted PDFs are rejected with a clear message; scanned PDFs with no text layer report that OCR would be needed. |
| `.docx` | python-docx | Paragraphs in document order, plus table rows. |
| `.txt` | Python stdlib | UTF-8 first (BOM-aware), then a safe latin-1 fallback, so decoding never crashes. |
| `.md` | Python stdlib | Read as text with headings and list markers left intact, since they are useful retrieval context. |

Uploads are validated three ways before parsing: extension, declared MIME type, and magic bytes — a renamed `.exe` is rejected even if it claims to be a PDF. Filenames are sanitised and client-supplied paths are never trusted.

## How chunking works

Chunking is character-based. A window of `chunk_size` characters is taken from the text, then the next window starts `chunk_size − overlap` characters after the previous one, so consecutive chunks share `overlap` characters of real text. With the defaults (size 1000, overlap 200) windows start at 0, 800, 1600, and so on.

Two refinements sit on top of the plain window. First, when a window would end mid-word, the cut is pulled back to the nearest natural boundary — paragraph break, then sentence ending, then line break, then any whitespace — searched within the last 20% of the window (capped at 300 characters), so chunk sizes stay close to the configured value. Second, chunks are trimmed and whitespace-only chunks are dropped, so nothing empty is ever embedded or stored.

The validation rule is `0 ≤ overlap < chunk_size`, enforced in the UI, in the Pydantic schema, and again in the chunking function itself. The UI computes `effective_max_overlap = min(2000, chunk_size − 1)` live, and lowering the chunk size below the current overlap pulls the overlap down automatically with a visible notice. The window always advances by at least one character per step, so the algorithm terminates even at `overlap = chunk_size − 1` — there is a test for exactly that case.

Every stored chunk carries metadata like:

```json
{
  "document_id": "6f1c…",
  "filename": "manual.pdf",
  "file_type": "pdf",
  "page": 5,
  "chunk_index": 12,
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "char_count": 978,
  "start_char": 9600,
  "end_char": 10578,
  "ingested_at": "2026-08-10T14:03:22+00:00"
}
```

Chunk IDs are stable and unique: `{document_id}_chunk_{chunk_index}`.

## Embedding configuration

The pipeline only ever talks to the `EmbeddingProvider` interface (`embed_documents`, `embed_query`, `dimension`). The default implementation wraps sentence-transformers with `all-MiniLM-L6-v2`, loads weights lazily and exactly once per process, normalises vectors, and embeds in configurable batches rather than one chunk at a time. Adding another backend — OpenAI embeddings, for example — means writing one subclass and registering it in `build_provider()` in `app/services/embeddings.py`; ingestion, storage, and search do not change.

A second provider, `hashing`, ships for testing: a deterministic bag-of-words vector space with no model download, which is what lets the full test suite run offline in seconds. It is never the default.

Because vectors are always computed by the app and handed to Chroma pre-built, Chroma never downloads or runs an embedding model of its own, and query vectors are guaranteed to come from the same model as the stored chunks.

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/ingest` | Multipart upload with `files`, `chunk_size`, `chunk_overlap`, `collection_name`; returns per-file results, statistics, and chunk previews |
| `GET /api/collections` | List collections with chunk counts |
| `POST /api/collections` | Create a collection |
| `GET /api/collections/{name}/stats` | Chunk count, document count, filenames |
| `GET /api/collections/{name}/chunks` | Page through stored chunks (`limit`, `offset`) |
| `DELETE /api/collections/{name}` | Delete a collection (UI asks for confirmation first) |
| `POST /api/search` | Embed a query and return the top-K nearest chunks with similarity scores |
| `GET /api/config` | Limits and defaults the frontend mirrors |
| `GET /api/health` | Liveness check |

Errors always arrive as `{ "success": false, "code": "...", "message": "..." }` with a message that is safe to show a user; stack traces and server paths are logged server-side only.

## Development commands

```bash
# Backend
cd backend
pytest                       # 62 tests: chunking, loaders, full API over ChromaDB
uvicorn app.main:app --reload

# Frontend
cd frontend
npm run dev                  # dev server on :3000
npm run typecheck            # strict tsc, no emit
npm run build                # production build
```

The API tests exercise the real pipeline — real multipart uploads, real PDF/DOCX bytes built at test time, real ChromaDB persistence in a temp directory — with only the embedding provider swapped for the deterministic `hashing` one so the suite needs no network or model download.

## Resetting data

Everything the app stores lives under `CHROMA_DIR` (default `backend/data/chroma`). Delete that directory, or delete individual collections from the UI, to start clean. Original uploaded files are never kept on the server; only extracted chunks and vectors are stored.

## Known limitations

Re-ingesting the same file creates a new document ID, so its chunks are stored again rather than replacing the previous copy — delete the collection or use a fresh one when re-indexing after settings changes. Scanned PDFs without a text layer are rejected with an explanatory error rather than OCR'd. Processing runs synchronously per request (kept off the event loop in a threadpool); the pipeline's step functions are deliberately separable so a job queue can be introduced later without restructuring.
