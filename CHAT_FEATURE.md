# What's new: Ask the assistant (BYOK chat)

Added a chat panel that answers questions in natural language, grounded in
whatever collection is selected — the "Generation" half of RAG, on top of the
"Retrieval" you already had working.

## How it works

1. You type a question and hit Ask.
2. The backend does the exact same retrieval as `/api/search` (embed your
   question locally, find the closest chunks in ChromaDB — no API key needed
   for this part).
3. Those chunks, plus your question, get sent to whichever provider you
   picked (OpenAI, Anthropic, or Gemini), with an instruction to answer using
   only what was found.
4. The provider's answer comes back and is shown in the chat, with the
   sources it was built from underneath.

## BYOK (Bring Your Own Key)

- Pick a provider from the dropdown, paste your own API key for that
  provider. Nothing is pre-configured — you supply the key.
- The key is sent once, per question, straight from your browser to this
  app's backend to the provider you chose. It's held in `sessionStorage`
  (cleared when you close the tab) purely so you don't retype it between
  questions — it is never written to disk, logged, or stored in ChromaDB.
- Model field is optional — leave it blank to use a sensible default
  (`gpt-4o-mini`, `claude-3-5-sonnet-latest`, or `gemini-2.0-flash`), or type
  a specific model name your account has access to.

## What changed under the hood

**Backend**
- `app/services/llm_providers.py` — new. One async function per provider
  (`_call_openai`, `_call_anthropic`, `_call_gemini`), all behind a single
  `generate_answer()` entry point, so adding a fourth provider later means
  writing one function, not touching the API route.
- `app/api/chat.py` — new. `POST /api/chat`: does retrieval (reusing the
  existing vector store + embedding provider dependencies), builds a prompt
  from the matched chunks, calls the chosen provider, returns the answer +
  sources.
- `app/models/schemas.py` — added `ChatRequest`, `ChatResponse`, `ChatSource`,
  `ChatMessage`.
- `app/core/errors.py` — added `MissingApiKey`, `InvalidApiKey`,
  `LLMProviderError`, `NoResultsFound`, so a bad key or a down provider
  surfaces as a clean `{code, message}` error, same as every other endpoint.
- `pyproject.toml` — `httpx` moved from dev-only to a real dependency (used
  to call the three providers' HTTP APIs directly, no extra SDKs).
- `tests/test_chat.py` — new, 6 tests. The outbound LLM call is stubbed so
  the whole suite still runs offline with zero API keys or network access,
  same philosophy as the hashing embedding provider used elsewhere in the
  tests. All 69 tests (63 original + 6 new) pass.

**Frontend**
- `components/ChatPanel.tsx` — new. Provider selector, API key field (with
  show/hide), optional model override, scrolling conversation view, source
  citations per answer.
- `lib/types.ts` / `lib/api.ts` — added `LlmProvider`, `ChatResponse`,
  `ChatTurn` types and the `askChat()` client function.
- `app/page.tsx` — added the new panel; updated the footer disclaimer, since
  it's no longer accurate to say nothing ever leaves the machine — ingestion,
  chunking, embedding, and search still do stay fully local, but the new chat
  panel intentionally sends matched excerpts to whichever provider you pick.

## Verified before delivery

Ran for real, not just written: `pip install -e ".[dev]"`, `pytest` (69/69
pass), booted the server and hit `/api/chat` directly, `npm install`,
`npx tsc --noEmit` (clean), `npm run build` (compiles, production build
succeeds). Only thing not testable in this environment: a real answer from
a live provider, since that needs your own API key and outbound internet
access this sandbox doesn't have — that part you'll confirm on your machine.

## Known limitations

- No streaming — the answer appears all at once when the provider finishes,
  not word-by-word.
- Conversation history is sent to the provider but not persisted anywhere —
  refreshing the page clears the chat.
- No per-provider token/cost display; you're relying on your own provider
  dashboard to track usage against your key.
