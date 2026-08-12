"use client";

import type { FileStatus, QueuedFile } from "@/lib/types";
import { formatBytes, formatNumber } from "@/lib/format";
import {
  Button,
  IconAlert,
  IconCheck,
  IconFile,
  IconTrash,
  ProgressBar,
  Spinner,
  StatusChip,
} from "./Primitives";

const STATUS_LABEL: Record<FileStatus, string> = {
  ready: "Ready",
  uploading: "Uploading",
  extracting: "Extracting",
  chunking: "Chunking",
  embedding: "Embedding",
  indexed: "Indexed",
  error: "Error",
};

const BUSY: ReadonlySet<FileStatus> = new Set<FileStatus>([
  "uploading",
  "extracting",
  "chunking",
  "embedding",
]);

function toneFor(status: FileStatus): "neutral" | "busy" | "success" | "error" {
  if (status === "indexed") return "success";
  if (status === "error") return "error";
  if (BUSY.has(status)) return "busy";
  return "neutral";
}

function iconFor(status: FileStatus) {
  if (status === "indexed") return <IconCheck width={12} height={12} />;
  if (status === "error") return <IconAlert width={12} height={12} />;
  if (BUSY.has(status)) return <Spinner className="h-3 w-3" />;
  return null;
}

interface FileListProps {
  files: QueuedFile[];
  onRemove: (id: string) => void;
  onClearAll: () => void;
  isProcessing: boolean;
}

export function FileList({ files, onRemove, onClearAll, isProcessing }: FileListProps) {
  if (files.length === 0) return null;

  const indexed = files.filter((file) => file.status === "indexed").length;

  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-ink-800">
          {files.length} {files.length === 1 ? "file" : "files"}
          {indexed > 0 ? <span className="text-ink-500"> · {indexed} indexed</span> : null}
        </h3>
        <Button variant="ghost" size="sm" onClick={onClearAll} disabled={isProcessing}>
          Clear all
        </Button>
      </div>

      <ul className="space-y-2">
        {files.map((file) => (
          <li
            key={file.id}
            className="animate-fade-up rounded-xl bg-ink-50 p-3 ring-1 ring-inset ring-ink-100"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-ink-400 shadow-sm">
                <IconFile width={16} height={16} />
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink-900" title={file.name}>
                  {file.name}
                </p>
                <p className="mt-0.5 text-xs text-ink-500">
                  <span className="font-mono uppercase">{file.extension || "file"}</span>
                  <span aria-hidden="true"> · </span>
                  {formatBytes(file.size)}
                  {file.status === "indexed" ? (
                    <>
                      <span aria-hidden="true"> · </span>
                      {formatNumber(file.chunksCreated)} chunks
                      {file.pages ? ` · ${file.pages} pages` : ""}
                    </>
                  ) : null}
                </p>
              </div>

              <StatusChip
                label={STATUS_LABEL[file.status]}
                tone={toneFor(file.status)}
                icon={iconFor(file.status)}
              />

              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRemove(file.id)}
                disabled={isProcessing}
                aria-label={`Remove ${file.name}`}
              >
                <IconTrash width={14} height={14} />
              </Button>
            </div>

            {file.status === "uploading" ? (
              <div className="mt-3">
                <ProgressBar
                  value={file.uploadProgress}
                  label={`Uploading ${file.name}`}
                />
              </div>
            ) : null}

            {file.status === "error" && file.error ? (
              <p className="mt-2 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800">
                <IconAlert width={14} height={14} className="mt-px shrink-0" />
                <span>{file.error}</span>
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
