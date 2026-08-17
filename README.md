# Document Embedding Studio

A local-first application for building the ingestion side of a **RAG
(Retrieval-Augmented Generation)** system — the part that lets an AI answer
questions using *your own documents* instead of only its general training
knowledge.

Drop in PDF, DOCX, Markdown, or plain-text files → the app extracts the
text, splits it into overlapping chunks, embeds every chunk with a local AI
model, and stores vectors + text + metadata in a persistent ChromaDB
collection. From there you can search semantically (by meaning, not just
keywords), or ask a chatbot to answer questions grounded in what's indexed.

**No paid API keys are required for the core pipeline.** Embedding and
retrieval run entirely on your own machine. The optional chat feature is
Bring-Your-Own-Key, so nothing is sent anywhere unless you explicitly choose
to use it.

## What it does, at a glance

| Capability | How it works | Runs where |
| --- | --- | --- |
| **Ingestion pipeline** | Upload → extract → clean → chunk → embed → store | Fully local |
| **Semantic search** | Query by meaning, not exact keywords, against ChromaDB | Fully local |
| **Ask the assistant (BYOK)** | Retrieval + your own OpenAI / Anthropic / Gemini key writes a real answer | Local retrieval, then your chosen provider |
| **Container status** | Live CPU/memory for the app's own Docker containers, pushed over a WebSocket | Fully local (Docker only) |

## How this was built

This started as a from-scratch FastAPI + Next.js + ChromaDB pipeline
(upload, chunking, embeddings, semantic search) — the ingestion side of RAG.
On top of that:

- **BYOK chat** was added so the app can also *answer* questions in plain
  language, not just return matching chunks — the "Generation" half of RAG.
  The person asking supplies their own API key for OpenAI, Anthropic, or
  Gemini; the key is never stored server-side, only used per-request.
- **A live container status panel** was added to make containerization
  visible and concrete: two Docker containers (backend, frontend) reporting
  their own real-time CPU and memory over a WebSocket, right inside the app.
- Both were built with tests that run offline (LLM calls and Docker stats
  are mocked in the test suite), so the whole thing can be verified without
  needing real API keys or a running Docker daemon.

## Architecture

```
Upload → Validate → Extract text → Clean text → Chunk → Metadata → Embed → Store in ChromaDB → Report
                                                                                   ↓
                                                                     Semantic search / Ask the assistant
```

The backend is FastAPI with a strict separation of concerns — extraction,
chunking, embeddings, and vector storage are independent modules, composed
by a single pipeline function. The frontend is Next.js (App Router) with
strict TypeScript.

```
backend/
  app/
    main.py                 FastAPI app, error handlers, /api/health, /api/config
    api/
      ingestion.py          POST /api/ingest (multipart upload)
      collections.py        list / create / stats / chunks / delete
      search.py             POST /api/search
      chat.py                POST /api/chat — retrieval + BYOK generation
      monitor.py              WS /ws/containers — live Docker container stats
      deps.py                dependency wiring (overridable in tests)
    services/
      document_loader.py    PDF, DOCX, TXT, MD extraction + sanitisation
      chunking.py            character windows, overlap, boundary snapping
      embeddings.py           EmbeddingProvider + SentenceTransformer impl
      vector_store.py         persistent ChromaDB facade
      pipeline.py              orchestration of the steps above
      llm_providers.py         BYOK OpenAI / Anthropic / Gemini calls
      docker_monitor.py        reads Docker socket for live container stats
    models/schemas.py       Pydantic request/response models
    core/config.py           settings from environment / .env
    core/errors.py           safe, typed domain errors
  tests/                    71 tests: chunking, loaders, full API, chat, monitor
  pyproject.toml
  .env.example
  Dockerfile

frontend/
  app/                      layout, page, global styles
  components/
    FileDropzone.tsx        keyboard-accessible drag & drop
    FileList.tsx             per-file status, progress, errors
    ChunkSettings.tsx        size + overlap sliders with live validation
    CollectionSelector.tsx   select / create / delete (with confirmation)
    ProcessingStatus.tsx      progress and run statistics
    ChunkPreview.tsx          chunk cards with real overlap highlighting
    SearchTester.tsx          semantic search panel
    ChatPanel.tsx              BYOK chat: provider picker, key field, conversation
    ContainerMonitor.tsx        live container status cards, via WebSocket
    Primitives.tsx              buttons, alerts, icons, progress bars
  lib/                      typed API client, shared types, helpers
  package.json
  Dockerfile

docker-compose.yml
```

## Requirements

Python 3.12 or newer, Node.js 20 or newer, and roughly 3 GB of disk for the
Python ML dependencies (sentence-transformers pulls in PyTorch). The
embedding model itself (~90 MB) downloads automatically on first use and is
cached afterwards. Docker Desktop is only required for the container status
panel and the one-command Docker workflow below — everything else runs fine
without it.

## Quick start (manual, two terminals)

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

Open http://localhost:3000. The first "Process & embed" run downloads the
embedding model, so it takes a minute; every run after that is fast.
Interactive API docs are at http://localhost:8000/docs.

Note: the **Container status** panel will show "Docker not reachable" in
this manual mode — it specifically needs the Docker socket, which is only
available when running via `docker compose up` (below). Everything else
works identically either way.

## Docker (recommended for the full experience, container status included)

```bash
docker compose up --build
```

This builds both images and starts the stack — frontend on port 3000,
backend on port 8000. First run takes several minutes (PyTorch and friends);
subsequent runs with plain `docker compose up` (no `--build`) start in
seconds, since the images are already built.

Vectors persist in the `chroma-data` named volume and model weights in
`hf-cache`, so both survive `docker compose down`. Both containers carry a
`studio.monitor` label, which is how the Container status panel finds them —
by label, not by hardcoded name, so this works regardless of the folder or
Compose project name.

**Security note on the container monitor:** the backend container is given
read access to the Docker socket (`/var/run/docker.sock`) so it can report
CPU/memory for its own containers. This is a real privilege — anything with
socket access can, in principle, control any container on the host, not
just these two. Fine for a local, single-user setup like this one; not
something to expose beyond your own machine. Full detail in
`CONTAINER_MONITOR_FEATURE.md`.

To stop: `Ctrl+C` in that terminal, or `docker compose down` from another one.

## Ask the assistant (BYOK chat)

The "Ask the assistant" panel answers questions in natural language,
grounded in whatever collection is selected:

1. Your question is embedded and matched against ChromaDB — same retrieval
   as the Search panel, fully local, no key needed for this part.
2. The matched chunks + your question are sent to whichever provider you
   pick (OpenAI, Anthropic, or Gemini), with an instruction to answer using
   only what was retrieved.
3. The answer streams back into the chat, with the source chunks listed
   underneath.

Pick a provider, paste your own API key for it (kept only in that browser
tab's session storage — cleared when the tab closes, never written to disk
or logged), optionally override the model, and ask. Full detail, including
exactly what changed in the codebase, is in `CHAT_FEATURE.md`.

## Container status (live, via WebSocket)

A small panel showing this app's own two Docker containers — status, CPU %,
memory used/limit — updating every 2 seconds over a WebSocket connection.
Purely observational: it reads stats, it never starts, stops, or restarts
anything. Full detail in `CONTAINER_MONITOR_FEATURE.md`.

## Configuration

The backend reads settings from environment variables or a `.env` file —
copy `backend/.env.example` to get started. Defaults are sensible, so no
configuration is required for local use.

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

The frontend has a single required variable, `NEXT_PUBLIC_API_URL`, in
`frontend/.env.local.example` — the WebSocket URL for the container panel is
derived automatically from it, no separate config needed. BYOK API keys are
entered in the UI at chat time, never stored in any `.env` file.

## Supported file formats

| Format | Parser | Notes |
| --- | --- | --- |
| `.pdf` | PyMuPDF | Text extracted per page; every chunk keeps its source page number. Encrypted PDFs are rejected with a clear message; scanned PDFs with no text layer report that OCR would be needed. |
| `.docx` | python-docx | Paragraphs in document order, plus table rows. |
| `.txt` | Python stdlib | UTF-8 first (BOM-aware), then a safe latin-1 fallback, so decoding never crashes. |
| `.md` | Python stdlib | Read as text with headings and list markers left intact, since they are useful retrieval context. |

Uploads are validated three ways before parsing: extension, declared MIME
type, and magic bytes — a renamed `.exe` is rejected even if it claims to be
a PDF.

## How chunking works

Chunking is character-based. A window of `chunk_size` characters is taken
from the text, then the next window starts `chunk_size − overlap` characters
after the previous one, so consecutive chunks share `overlap` characters of
real text.

Two refinements sit on top of the plain window. First, when a window would
end mid-word, the cut is pulled back to the nearest natural boundary —
paragraph break, then sentence ending, then line break, then any whitespace
— so chunk sizes stay close to the configured value without cutting words in
half. Second, chunks are trimmed and whitespace-only chunks are dropped.

Validation rule: `0 ≤ overlap < chunk_size`, enforced in the UI, in the
Pydantic schema, and again inside the chunking function itself. The window
always advances by at least one character per step, so the algorithm cannot
loop forever even at the pathological edge case `overlap = chunk_size − 1`
— there's a dedicated test for exactly that.

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/ingest` | Multipart upload; returns per-file results, statistics, chunk previews |
| `GET /api/collections` | List collections with chunk counts |
| `POST /api/collections` | Create a collection |
| `GET /api/collections/{name}/stats` | Chunk count, document count, filenames |
| `GET /api/collections/{name}/chunks` | Page through stored chunks |
| `DELETE /api/collections/{name}` | Delete a collection (UI asks for confirmation first) |
| `POST /api/search` | Embed a query, return top-K nearest chunks with similarity scores |
| `POST /api/chat` | Retrieval + BYOK generation — a written answer, grounded in retrieved chunks |
| `WS /ws/containers` | Live container status, pushed every 2 seconds |
| `GET /api/config` | Limits and defaults the frontend mirrors |
| `GET /api/health` | Liveness check |

Errors always arrive as `{ "success": false, "code": "...", "message": "..." }`.

## Development commands

```bash
# Backend
cd backend
pytest                       # 71 tests — chunking, loaders, ingest/search/chat/monitor API
uvicorn app.main:app --reload

# Frontend
cd frontend
npm run dev                  # dev server on :3000
npx tsc --noEmit              # strict type-check
npm run build                 # production build
```

The chat and container-monitor tests mock the outbound LLM call and the
Docker socket respectively, so the full suite runs offline — no real API
keys and no running Docker daemon required to verify the code.

## Known limitations

- Re-ingesting the same file creates a new document ID rather than replacing
  the previous copy — delete the collection or use a fresh one when
  re-indexing after settings changes.
- Scanned PDFs without a text layer are rejected with an explanatory error
  rather than OCR'd.
- Chat has no streaming (the answer appears all at once) and no persisted
  history (refreshing the page clears the conversation).
- The container panel only shows this app's own two containers, by design —
  not a general-purpose Docker dashboard — and needs `docker compose up`
  specifically to work at all.

## Further reading

- `CHAT_FEATURE.md` — exactly what changed to add BYOK chat, file by file.
- `CONTAINER_MONITOR_FEATURE.md` — exactly what changed to add the container
  panel, including the Docker socket security trade-off in full detail.
