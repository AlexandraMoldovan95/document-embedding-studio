"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ApiError, askChat } from "@/lib/api";
import { LLM_PROVIDERS, type ChatTurn, type LlmProvider } from "@/lib/types";
import { Alert, Button, EmptyState, IconSpark, Spinner } from "./Primitives";

interface ChatPanelProps {
  collectionName: string;
  chunkCount: number;
}

const STORAGE_PREFIX = "des_byok_"; // sessionStorage only — cleared when the tab closes.

export function ChatPanel({ collectionName, chunkCount }: ChatPanelProps) {
  const queryId = useId();

  const [provider, setProvider] = useState<LlmProvider>("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [showKey, setShowKey] = useState(false);

  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Restore this provider's key for the current browser tab only.
  useEffect(() => {
    const saved = sessionStorage.getItem(`${STORAGE_PREFIX}${provider}`);
    setApiKey(saved ?? "");
    setModel("");
  }, [provider]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, isAsking]);

  const rememberKey = (value: string) => {
    setApiKey(value);
    if (value) sessionStorage.setItem(`${STORAGE_PREFIX}${provider}`, value);
    else sessionStorage.removeItem(`${STORAGE_PREFIX}${provider}`);
  };

  const activeProvider = LLM_PROVIDERS.find((p) => p.id === provider)!;

  const canAsk = question.trim().length > 0 && apiKey.trim().length > 0 && !isAsking;

  const ask = async () => {
    const trimmed = question.trim();
    if (!trimmed || !apiKey.trim() || isAsking) return;

    const userTurn: ChatTurn = { id: crypto.randomUUID(), role: "user", content: trimmed };
    setTurns((prev) => [...prev, userTurn]);
    setQuestion("");
    setIsAsking(true);
    setError(null);

    try {
      const response = await askChat({
        query: trimmed,
        collectionName,
        topK: 5,
        provider,
        apiKey: apiKey.trim(),
        model: model.trim(),
        history: turns.slice(-8).map((t) => ({ role: t.role, content: t.content })),
      });
      setTurns((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          sources: response.sources,
        },
      ]);
    } catch (askError) {
      const message =
        askError instanceof ApiError ? askError.message : "The assistant could not answer that.";
      setError(message);
      setTurns((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: "", error: message },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div>
      {/* Provider + key ------------------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-[1fr_2fr_1fr]">
        <div>
          <label htmlFor={`${queryId}-provider`} className="field-label">
            Provider
          </label>
          <select
            id={`${queryId}-provider`}
            className="text-input mt-2"
            value={provider}
            onChange={(event) => setProvider(event.target.value as LlmProvider)}
            disabled={isAsking}
          >
            {LLM_PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={`${queryId}-key`} className="field-label">
            {activeProvider.label} API key
          </label>
          <div className="relative mt-2">
            <input
              id={`${queryId}-key`}
              type={showKey ? "text" : "password"}
              autoComplete="off"
              className="text-input pr-16 font-mono"
              placeholder="sk-..."
              value={apiKey}
              onChange={(event) => rememberKey(event.target.value)}
              disabled={isAsking}
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-ink-500 hover:text-ink-800"
            >
              {showKey ? "Hide" : "Show"}
            </button>
          </div>
        </div>

        <div>
          <label htmlFor={`${queryId}-model`} className="field-label">
            Model
            <span className="ml-1 font-normal text-ink-400">(optional)</span>
          </label>
          <input
            id={`${queryId}-model`}
            type="text"
            className="text-input mt-2 font-mono"
            placeholder={activeProvider.defaultModel}
            value={model}
            onChange={(event) => setModel(event.target.value)}
            disabled={isAsking}
          />
        </div>
      </div>

      <p className="mt-2 text-xs text-ink-500">
        Your key is sent straight to {activeProvider.label} with each question, kept only in this
        browser tab (cleared when you close it), and never stored on this app&apos;s server.
        Retrieval still runs against <span className="font-mono">{collectionName}</span>
        {chunkCount > 0 ? ` (${chunkCount} chunks indexed)` : " (nothing indexed yet)"} — but
        generating an answer sends the matched excerpts to {activeProvider.label}, unlike Search
        above, which stays fully local.
      </p>

      {/* Conversation ----------------------------------------------------- */}
      <div
        ref={scrollRef}
        className="mt-5 max-h-[28rem] space-y-4 overflow-y-auto rounded-xl bg-ink-50 p-4"
      >
        {turns.length === 0 ? (
          <EmptyState
            icon={<IconSpark width={28} height={28} />}
            title={chunkCount > 0 ? "Ask a question" : "Nothing indexed yet"}
            description={
              chunkCount > 0
                ? "The assistant answers only from what's indexed in this collection, in plain, detailed language."
                : "Process a document first, then come back and ask about it."
            }
          />
        ) : (
          turns.map((turn) => <ChatBubble key={turn.id} turn={turn} />)
        )}
        {isAsking ? (
          <div className="flex items-center gap-2 text-xs text-ink-500">
            <Spinner /> Searching the collection and asking {activeProvider.label}…
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}

      {/* Input -------------------------------------------------------- */}
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor={`${queryId}-question`} className="sr-only">
            Ask a question about your documents
          </label>
          <input
            id={`${queryId}-question`}
            type="text"
            className="text-input"
            placeholder="Ask a question about your documents…"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void ask();
            }}
            disabled={isAsking}
          />
        </div>
        <Button
          variant="primary"
          size="md"
          className="h-[38px]"
          onClick={() => void ask()}
          disabled={!canAsk}
        >
          {isAsking ? <Spinner /> : null}
          Ask
        </Button>
      </div>
    </div>
  );
}

function ChatBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-xl px-4 py-3 text-sm ${
          isUser
            ? "bg-accent-600 text-white"
            : turn.error
              ? "bg-red-50 text-red-900 ring-1 ring-inset ring-red-100"
              : "bg-white text-ink-800 ring-1 ring-inset ring-ink-100"
        }`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{turn.error ?? turn.content}</p>

        {turn.sources && turn.sources.length > 0 ? (
          <details className="mt-3">
            <summary className="cursor-pointer text-xs font-medium text-ink-500 hover:text-ink-800">
              {turn.sources.length} source{turn.sources.length > 1 ? "s" : ""}
            </summary>
            <ul className="mt-2 space-y-2">
              {turn.sources.map((source, index) => (
                <li key={index} className="rounded-lg bg-ink-50 p-2 text-xs text-ink-600">
                  <span className="font-medium text-ink-800">{source.filename}</span>
                  {source.page !== null ? ` · Page ${source.page}` : ""}
                  {" · Score "}
                  {source.score.toFixed(2)}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </div>
  );
}
