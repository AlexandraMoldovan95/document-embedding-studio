"use client";

import { useId, useState } from "react";
import { ApiError, search } from "@/lib/api";
import type { SearchResult } from "@/lib/types";
import { clamp, formatNumber } from "@/lib/format";
import { Alert, Button, EmptyState, IconSearch, Spinner } from "./Primitives";

interface SearchTesterProps {
  collectionName: string;
  /** Chunk count in the selected collection, used for the empty state. */
  chunkCount: number;
}

export function SearchTester({ collectionName, chunkCount }: SearchTesterProps) {
  const queryId = useId();
  const topKId = useId();

  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [tookMs, setTookMs] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed || isSearching) return;

    setIsSearching(true);
    setError(null);
    try {
      const response = await search({
        query: trimmed,
        collection_name: collectionName,
        top_k: topK,
      });
      setResults(response.results);
      setTookMs(response.took_ms);
    } catch (searchError) {
      setResults(null);
      setError(
        searchError instanceof ApiError
          ? searchError.message
          : "The search could not be completed.",
      );
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor={queryId} className="field-label">
            Search your documents
          </label>
          <div className="relative mt-2">
            <span
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400"
              aria-hidden="true"
            >
              <IconSearch />
            </span>
            <input
              id={queryId}
              type="search"
              className="text-input pl-9"
              placeholder="What does the contract say about late payment?"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runSearch();
              }}
            />
          </div>
        </div>

        <div className="w-24">
          <label htmlFor={topKId} className="field-label">
            Top K
          </label>
          <input
            id={topKId}
            type="number"
            min={1}
            max={50}
            className="text-input mt-2 font-mono"
            value={topK}
            onChange={(event) => setTopK(clamp(Number(event.target.value) || 1, 1, 50))}
          />
        </div>

        <Button
          variant="primary"
          size="md"
          className="h-[38px]"
          onClick={() => void runSearch()}
          disabled={isSearching || query.trim().length === 0}
        >
          {isSearching ? <Spinner /> : null}
          Search
        </Button>
      </div>

      <p className="mt-2 text-xs text-ink-500">
        Searching <span className="font-mono">{collectionName}</span>
        {chunkCount > 0 ? ` · ${formatNumber(chunkCount)} chunks indexed` : ""}
      </p>

      <div className="mt-5">
        {error ? <Alert tone="error">{error}</Alert> : null}

        {!error && results === null ? (
          <EmptyState
            icon={<IconSearch width={28} height={28} />}
            title={chunkCount > 0 ? "Try a question" : "Nothing indexed yet"}
            description={
              chunkCount > 0
                ? "Ask in your own words. The query is embedded with the same model as your chunks, so wording does not have to match."
                : "Process a document first, then come back and search it."
            }
          />
        ) : null}

        {!error && results !== null && results.length === 0 ? (
          <EmptyState
            icon={<IconSearch width={28} height={28} />}
            title="No matches"
            description="This collection has no chunks yet, or nothing came close enough to return."
          />
        ) : null}

        {results && results.length > 0 ? (
          <>
            <p className="mb-3 text-xs text-ink-500">
              {results.length} {results.length === 1 ? "result" : "results"} in{" "}
              {tookMs.toFixed(0)} ms
            </p>
            <ol className="space-y-3">
              {results.map((result) => (
                <li
                  key={result.id}
                  className="animate-fade-up rounded-xl bg-ink-50 p-4 ring-1 ring-inset ring-ink-100"
                >
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="font-mono text-xs font-semibold text-ink-900">
                      Result #{result.rank}
                    </span>
                    <ScoreBadge score={result.score} />
                    <span className="text-xs text-ink-500">
                      {result.filename}
                      {result.page !== null ? ` · Page ${result.page}` : ""}
                      {result.chunk_index !== null ? ` · Chunk ${result.chunk_index}` : ""}
                    </span>
                  </div>
                  <p className="mt-3 line-clamp-6 whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-ink-700">
                    {result.text}
                  </p>
                </li>
              ))}
            </ol>
          </>
        ) : null}
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-2 py-0.5 text-xs shadow-sm">
      <span className="text-ink-500">Score</span>
      <span className="font-mono font-semibold tabular-nums text-ink-900">
        {score.toFixed(2)}
      </span>
      <span
        className="h-1.5 w-10 overflow-hidden rounded-full bg-ink-100"
        aria-hidden="true"
      >
        <span
          className="block h-full rounded-full bg-accent-500"
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </span>
    </span>
  );
}
