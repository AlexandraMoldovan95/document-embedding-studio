"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { CollectionInfo } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import { Alert, Button, IconDatabase, IconTrash, Spinner } from "./Primitives";

interface CollectionSelectorProps {
  collections: CollectionInfo[];
  selected: string;
  loading: boolean;
  error: string | null;
  disabled?: boolean;
  onSelect: (name: string) => void;
  onCreate: (name: string) => Promise<void>;
  onDelete: (name: string) => Promise<void>;
}

export function CollectionSelector({
  collections,
  selected,
  loading,
  error,
  disabled = false,
  onSelect,
  onCreate,
  onDelete,
}: CollectionSelectorProps) {
  const selectId = useId();
  const newNameId = useId();

  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<CollectionInfo | null>(null);

  const current = collections.find((collection) => collection.name === selected);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      setCreateError("Enter a name for the collection.");
      return;
    }
    setBusy(true);
    setCreateError(null);
    try {
      await onCreate(name);
      setNewName("");
      setIsCreating(false);
    } catch (creationError) {
      setCreateError(
        creationError instanceof Error ? creationError.message : "The collection was not created.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    setBusy(true);
    try {
      await onDelete(pendingDelete.name);
      setPendingDelete(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <label htmlFor={selectId} className="field-label">
        Collection
      </label>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-ink-500">
          <Spinner /> Loading collections…
        </div>
      ) : (
        <div className="flex gap-2">
          <select
            id={selectId}
            className="text-input flex-1"
            value={selected}
            disabled={disabled || collections.length === 0}
            onChange={(event) => onSelect(event.target.value)}
          >
            {collections.length === 0 ? (
              <option value="">No collections yet</option>
            ) : (
              collections.map((collection) => (
                <option key={collection.name} value={collection.name}>
                  {collection.name} ({formatNumber(collection.chunk_count)})
                </option>
              ))
            )}
          </select>
          <Button
            onClick={() => setIsCreating((open) => !open)}
            disabled={disabled}
            aria-expanded={isCreating}
          >
            New
          </Button>
        </div>
      )}

      {current ? (
        <p className="flex items-center gap-2 text-xs text-ink-500">
          <IconDatabase width={14} height={14} />
          {formatNumber(current.chunk_count)} chunks stored
          <button
            type="button"
            className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-red-700 hover:bg-red-50 disabled:text-ink-300"
            onClick={() => setPendingDelete(current)}
            disabled={disabled}
          >
            <IconTrash width={12} height={12} />
            Delete
          </button>
        </p>
      ) : null}

      {isCreating ? (
        <div className="space-y-2 rounded-xl bg-ink-50 p-3">
          <label htmlFor={newNameId} className="text-xs font-medium text-ink-700">
            New collection name
          </label>
          <div className="flex gap-2">
            <input
              id={newNameId}
              className="text-input flex-1"
              value={newName}
              placeholder="research-notes"
              autoComplete="off"
              onChange={(event) => setNewName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleCreate();
              }}
            />
            <Button variant="primary" onClick={() => void handleCreate()} disabled={busy}>
              {busy ? <Spinner /> : null}
              Create
            </Button>
          </div>
          <p className="text-xs text-ink-500">
            3–63 characters. Letters, numbers, dots, dashes, and underscores.
          </p>
          {createError ? <Alert tone="error">{createError}</Alert> : null}
        </div>
      ) : null}

      {error ? <Alert tone="error">{error}</Alert> : null}

      {pendingDelete ? (
        <DeleteDialog
          collection={pendingDelete}
          busy={busy}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => void handleDelete()}
        />
      ) : null}
    </div>
  );
}

function DeleteDialog({
  collection,
  busy,
  onCancel,
  onConfirm,
}: {
  collection: CollectionInfo;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-panel"
      >
        <h3 id={titleId} className="text-base font-semibold text-ink-900">
          Delete &ldquo;{collection.name}&rdquo;?
        </h3>
        <p className="mt-2 text-sm text-ink-600">
          This permanently removes {formatNumber(collection.chunk_count)} indexed{" "}
          {collection.chunk_count === 1 ? "chunk" : "chunks"}. The original files on your
          computer are not touched.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button ref={cancelRef} onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={busy}>
            {busy ? <Spinner /> : null}
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
