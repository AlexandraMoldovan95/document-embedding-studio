"use client";

import type { RunSummary } from "@/lib/types";
import { formatDuration, formatNumber } from "@/lib/format";
import {
  Alert,
  EmptyState,
  IconAlert,
  IconCheck,
  IconLayers,
  ProgressBar,
  Spinner,
  cx,
} from "./Primitives";

export interface ProcessingState {
  /** Files finished so far in this run — a real count, not an estimate. */
  completed: number;
  total: number;
  currentFile: string | null;
  /** Upload percentage reported by the browser for the file in flight. */
  uploadPercent: number;
}

interface ProcessingStatusProps {
  isProcessing: boolean;
  progress: ProcessingState;
  summary: RunSummary | null;
  fatalError: string | null;
}

const PIPELINE_STEPS = [
  "Extracting text",
  "Creating chunks",
  "Generating embeddings",
  "Saving to ChromaDB",
] as const;

export function ProcessingStatus({
  isProcessing,
  progress,
  summary,
  fatalError,
}: ProcessingStatusProps) {
  if (fatalError && !isProcessing) {
    return <Alert tone="error" title="Processing stopped">{fatalError}</Alert>;
  }

  if (isProcessing) {
    const percent = progress.total > 0 ? (progress.completed / progress.total) * 100 : 0;
    return (
      <div aria-live="polite">
        <div className="flex items-center gap-3">
          <Spinner className="h-4 w-4 text-accent-600" />
          <p className="text-sm font-medium text-ink-900">
            Processing documents… {progress.completed} of {progress.total} done
          </p>
        </div>

        <div className="mt-4">
          <ProgressBar value={percent} label="Documents processed" />
        </div>

        {progress.currentFile ? (
          <div className="mt-5 rounded-xl bg-ink-50 p-4">
            <p className="truncate text-sm font-medium text-ink-800">
              {progress.currentFile}
            </p>

            {progress.uploadPercent < 100 ? (
              <div className="mt-3">
                <p className="mb-2 text-xs text-ink-500">
                  Uploading — {progress.uploadPercent}%
                </p>
                <ProgressBar
                  value={progress.uploadPercent}
                  label={`Uploading ${progress.currentFile}`}
                />
              </div>
            ) : (
              <ul className="mt-3 space-y-1.5">
                {PIPELINE_STEPS.map((step) => (
                  <li key={step} className="flex items-center gap-2 text-xs text-ink-600">
                    <Spinner className="h-3 w-3 text-accent-600" />
                    {step}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </div>
    );
  }

  if (!summary) {
    return (
      <EmptyState
        icon={<IconLayers width={28} height={28} />}
        title="No documents processed yet"
        description="Add files, set your chunk size and overlap, then select Process & embed."
      />
    );
  }

  const hasFailures = summary.documentsFailed > 0;

  return (
    <div className="animate-fade-up">
      <div className="flex items-center gap-2">
        <span
          className={cx(
            "flex h-7 w-7 items-center justify-center rounded-full",
            hasFailures ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700",
          )}
          aria-hidden="true"
        >
          {hasFailures ? <IconAlert width={14} height={14} /> : <IconCheck width={14} height={14} />}
        </span>
        <p className="text-sm font-medium text-ink-900">
          {hasFailures
            ? `Finished with ${summary.documentsFailed} ${summary.documentsFailed === 1 ? "file" : "files"} skipped`
            : "Processing complete"}
        </p>
        <span className="ml-auto text-xs text-ink-500">
          {formatDuration(summary.durationSeconds)}
        </span>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="Documents" value={formatNumber(summary.documentsProcessed)} />
        <Stat label="Characters" value={formatNumber(summary.charactersExtracted)} />
        <Stat label="Chunks" value={formatNumber(summary.chunksCreated)} />
        <Stat label="Embeddings" value={formatNumber(summary.embeddingsCreated)} />
        <Stat label="Collection" value={summary.collection} mono={false} />
      </dl>

      {summary.embeddingModel ? (
        <p className="mt-3 text-xs text-ink-500">
          Embedded with <span className="font-mono">{summary.embeddingModel}</span>
        </p>
      ) : null}

      {summary.errors.length > 0 ? (
        <div className="mt-5 space-y-2">
          {summary.errors.map((error) => (
            <Alert key={`${error.filename}-${error.code}`} tone="error" title={error.filename}>
              {error.message}
            </Alert>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  mono = true,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl bg-ink-50 px-4 py-3">
      <dt className="text-xs text-ink-500">{label}</dt>
      <dd
        className={cx(
          "mt-1 truncate text-lg font-semibold text-ink-900",
          mono && "font-mono tabular-nums",
        )}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}
