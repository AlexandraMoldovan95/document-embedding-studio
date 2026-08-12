"use client";

import { useCallback, useRef, useState } from "react";
import type { DragEvent, KeyboardEvent } from "react";
import { Button, IconUpload, cx } from "./Primitives";

interface FileDropzoneProps {
  onFilesAdded: (files: File[]) => void;
  supportedExtensions: string[];
  maxFileSizeMb: number;
  disabled?: boolean;
}

export function FileDropzone({
  onFilesAdded,
  supportedExtensions,
  maxFileSizeMb,
  disabled = false,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  // Drag events fire for child elements too; counting keeps the highlight stable.
  const dragDepth = useRef(0);

  const accept = supportedExtensions.map((extension) => `.${extension}`).join(",");

  const openPicker = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  };

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) return;
    dragDepth.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    if (disabled) return;
    const dropped = Array.from(event.dataTransfer.files);
    if (dropped.length > 0) onFilesAdded(dropped);
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label={`Add documents. Drop files here or press Enter to browse. Supported formats: ${supportedExtensions.join(", ")}.`}
        onClick={openPicker}
        onKeyDown={handleKeyDown}
        onDragEnter={handleDragEnter}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cx(
          "flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-2xl px-6 py-10 text-center transition-colors",
          "bg-ink-50 ring-1 ring-inset ring-ink-200/70",
          isDragging && "bg-accent-50 ring-2 ring-accent-500",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <span
          className={cx(
            "mb-4 flex h-12 w-12 items-center justify-center rounded-xl transition-colors",
            isDragging ? "bg-accent-600 text-white" : "bg-white text-ink-400 shadow-sm",
          )}
        >
          <IconUpload width={22} height={22} />
        </span>

        <p className="text-base font-medium text-ink-900">
          {isDragging ? "Drop to add these files" : "Drag & drop documents here"}
        </p>
        <p className="mt-1 text-sm text-ink-500">
          {supportedExtensions.map((extension) => `.${extension}`).join("  ·  ")} — up to{" "}
          {maxFileSizeMb} MB each
        </p>

        <Button
          className="mt-5"
          onClick={(event) => {
            event.stopPropagation();
            openPicker();
          }}
          disabled={disabled}
          tabIndex={-1}
        >
          Browse files
        </Button>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          const selected = Array.from(event.target.files ?? []);
          if (selected.length > 0) onFilesAdded(selected);
          event.target.value = ""; // let the same file be re-selected later
        }}
      />
    </div>
  );
}
