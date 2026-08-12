"use client";

import { useEffect, useId, useMemo, useState } from "react";
import type { ChunkPreview as Chunk } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import {
  Button,
  EmptyState,
  IconChevronLeft,
  IconChevronRight,
  IconLayers,
  Spinner,
} from "./Primitives";

/**
 * Longest suffix of `before` that is also a prefix of `after`.
 *
 * This is the overlap as it actually landed in the text, not the number the
 * slider was set to — boundary snapping can shift it — so the highlight shows
 * what was really stored.
 */
function sharedRegionLength(before: string, after: string, cap = 2000): number {
  const limit = Math.min(before.length, after.length, cap);
  for (let length = limit; length >= 8; length -= 1) {
    if (before.endsWith(after.slice(0, length))) return length;
  }
  return 0;
}

interface ChunkPreviewProps {
  chunks: Chunk[];
  loading?: boolean;
  totalInCollection?: number;
  emptyMessage?: string;
}

export function ChunkPreview({
  chunks,
  loading = false,
  totalInCollection,
  emptyMessage = "Process a document to see how it was split.",
}: ChunkPreviewProps) {
  const filterId = useId();
  const [filename, setFilename] = useState("all");
  const [index, setIndex] = useState(0);

  const filenames = useMemo(
    () => Array.from(new Set(chunks.map((chunk) => chunk.filename))).sort(),
    [chunks],
  );

  const visible = useMemo(
    () => (filename === "all" ? chunks : chunks.filter((chunk) => chunk.filename === filename)),
    [chunks, filename],
  );

  useEffect(() => setIndex(0), [filename, chunks]);

  const current = visible[index];
  const previous = index > 0 ? visible[index - 1] : undefined;
  const next = index < visible.length - 1 ? visible[index + 1] : undefined;

  const overlapWithPrevious =
    current && previous && previous.filename === current.filename
      ? sharedRegionLength(previous.text, current.text)
      : 0;
  const overlapWithNext =
    current && next && next.filename === current.filename
      ? sharedRegionLength(current.text, next.text)
      : 0;

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-ink-500">
        <Spinner /> Loading chunks…
      </div>
    );
  }

  if (chunks.length === 0) {
    return (
      <EmptyState
        icon={<IconLayers width={28} height={28} />}
        title="No chunks to preview"
        description={emptyMessage}
      />
    );
  }

  if (!current) {
    return (
      <EmptyState
        icon={<IconLayers width={28} height={28} />}
        title="No chunks from this file"
        description="Choose a different file in the filter above."
      />
    );
  }

  const head = current.text.slice(0, overlapWithPrevious);
  const body = current.text.slice(
    overlapWithPrevious,
    current.text.length - overlapWithNext,
  );
  const tail = overlapWithNext > 0 ? current.text.slice(current.text.length - overlapWithNext) : "";

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {filenames.length > 1 ? (
          <div className="flex items-center gap-2">
            <label htmlFor={filterId} className="text-xs text-ink-500">
              File
            </label>
            <select
              id={filterId}
              className="text-input w-auto py-1.5 text-xs"
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
            >
              <option value="all">All files ({chunks.length})</option>
              {filenames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <span className="text-xs text-ink-500">
            {formatNumber(chunks.length)} chunks shown
            {totalInCollection && totalInCollection > chunks.length
              ? ` of ${formatNumber(totalInCollection)} in this collection`
              : ""}
          </span>
        )}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => setIndex((value) => Math.max(0, value - 1))}
            disabled={index === 0}
            aria-label="Previous chunk"
          >
            <IconChevronLeft width={14} height={14} />
          </Button>
          <span className="min-w-[5.5rem] text-center font-mono text-xs tabular-nums text-ink-600">
            {index + 1} / {visible.length}
          </span>
          <Button
            size="sm"
            onClick={() => setIndex((value) => Math.min(visible.length - 1, value + 1))}
            disabled={index >= visible.length - 1}
            aria-label="Next chunk"
          >
            <IconChevronRight width={14} height={14} />
          </Button>
        </div>
      </div>

      <article
        className="mt-4 rounded-xl bg-ink-50 p-5 ring-1 ring-inset ring-ink-100"
        aria-live="polite"
      >
        <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-ink-200/60 pb-3">
          <h3 className="font-mono text-sm font-semibold text-ink-900">
            Chunk #{current.chunk_index}
          </h3>
          <p className="text-xs text-ink-500">
            <span className="text-ink-700">{current.filename}</span>
            {current.page !== null ? (
              <>
                <span aria-hidden="true"> · </span>Page {current.page}
              </>
            ) : null}
            <span aria-hidden="true"> · </span>
            {formatNumber(current.char_count)} characters
          </p>
        </header>

        <p className="mt-4 whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-ink-800">
          {head ? (
            <mark
              className="bg-accent-100 text-ink-900"
              title="Repeated from the previous chunk"
            >
              {head}
            </mark>
          ) : null}
          {body}
          {tail ? (
            <mark className="bg-accent-100 text-ink-900" title="Repeats into the next chunk">
              {tail}
            </mark>
          ) : null}
        </p>

        {head || tail ? (
          <p className="mt-4 text-xs text-ink-500">
            <span
              className="mr-1.5 inline-block h-2 w-2 rounded-sm bg-accent-200 align-middle"
              aria-hidden="true"
            />
            Highlighted text is the overlap this chunk shares with its neighbours.
          </p>
        ) : null}
      </article>
    </div>
  );
}
