"use client";

import { useEffect, useId, useState } from "react";
import { clamp, effectiveMaxOverlap, formatNumber } from "@/lib/format";
import { Alert } from "./Primitives";

export interface ChunkSettingsValue {
  chunkSize: number;
  chunkOverlap: number;
}

interface ChunkSettingsProps {
  value: ChunkSettingsValue;
  onChange: (value: ChunkSettingsValue) => void;
  minChunkSize: number;
  maxChunkSize: number;
  overlapCeiling: number;
  validationMessage: string | null;
  disabled?: boolean;
}

/**
 * Chunk size and overlap, each with a slider and a number input.
 *
 * The overlap ceiling is `min(overlapCeiling, chunkSize - 1)` and is recomputed
 * on every change, so an invalid pair can never be submitted. Lowering the
 * chunk size past the current overlap pulls the overlap down with it and says
 * so, rather than silently failing on submit.
 */
export function ChunkSettings({
  value,
  onChange,
  minChunkSize,
  maxChunkSize,
  overlapCeiling,
  validationMessage,
  disabled = false,
}: ChunkSettingsProps) {
  const sizeId = useId();
  const overlapId = useId();

  // Number inputs hold text while being typed so the field can go briefly empty.
  const [sizeText, setSizeText] = useState(String(value.chunkSize));
  const [overlapText, setOverlapText] = useState(String(value.chunkOverlap));
  const [autoAdjusted, setAutoAdjusted] = useState(false);

  useEffect(() => setSizeText(String(value.chunkSize)), [value.chunkSize]);
  useEffect(() => setOverlapText(String(value.chunkOverlap)), [value.chunkOverlap]);

  const maxOverlap = effectiveMaxOverlap(value.chunkSize, overlapCeiling);

  const applySize = (rawSize: number) => {
    const chunkSize = clamp(Math.round(rawSize), minChunkSize, maxChunkSize);
    const ceiling = effectiveMaxOverlap(chunkSize, overlapCeiling);
    const chunkOverlap = Math.min(value.chunkOverlap, ceiling);
    setAutoAdjusted(chunkOverlap !== value.chunkOverlap);
    onChange({ chunkSize, chunkOverlap });
  };

  const applyOverlap = (rawOverlap: number) => {
    setAutoAdjusted(false);
    onChange({
      chunkSize: value.chunkSize,
      chunkOverlap: clamp(Math.round(rawOverlap), 0, maxOverlap),
    });
  };

  const overlapPercent = Math.round((value.chunkOverlap / value.chunkSize) * 100);

  return (
    <div className="space-y-7">
      {/* Chunk size ------------------------------------------------------- */}
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={sizeId} className="field-label">
            Chunk size
          </label>
          <span className="text-xs text-ink-500">
            {formatNumber(minChunkSize)}–{formatNumber(maxChunkSize)}
          </span>
        </div>

        <div className="mt-3 flex items-center gap-3">
          <input
            id={sizeId}
            type="number"
            inputMode="numeric"
            min={minChunkSize}
            max={maxChunkSize}
            step={50}
            value={sizeText}
            disabled={disabled}
            aria-describedby={`${sizeId}-hint`}
            className="text-input w-28 font-mono"
            onChange={(event) => setSizeText(event.target.value)}
            onBlur={() => applySize(Number(sizeText) || value.chunkSize)}
            onKeyDown={(event) => {
              if (event.key === "Enter") applySize(Number(sizeText) || value.chunkSize);
            }}
          />
          <span id={`${sizeId}-hint`} className="text-sm text-ink-500">
            characters
          </span>
        </div>

        <input
          type="range"
          className="slider mt-4"
          min={minChunkSize}
          max={maxChunkSize}
          step={50}
          value={value.chunkSize}
          disabled={disabled}
          aria-label="Chunk size in characters"
          aria-valuetext={`${value.chunkSize} characters`}
          onChange={(event) => applySize(Number(event.target.value))}
        />
      </div>

      {/* Chunk overlap ---------------------------------------------------- */}
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={overlapId} className="field-label">
            Chunk overlap
          </label>
          <span className="text-xs text-ink-500">max {formatNumber(maxOverlap)}</span>
        </div>

        <div className="mt-3 flex items-center gap-3">
          <input
            id={overlapId}
            type="number"
            inputMode="numeric"
            min={0}
            max={maxOverlap}
            step={10}
            value={overlapText}
            disabled={disabled}
            aria-describedby={`${overlapId}-hint`}
            className="text-input w-28 font-mono"
            onChange={(event) => setOverlapText(event.target.value)}
            onBlur={() => applyOverlap(Number(overlapText) || 0)}
            onKeyDown={(event) => {
              if (event.key === "Enter") applyOverlap(Number(overlapText) || 0);
            }}
          />
          <span id={`${overlapId}-hint`} className="text-sm text-ink-500">
            characters
            {value.chunkOverlap > 0 ? (
              <span className="text-ink-400"> · {overlapPercent}% of each chunk</span>
            ) : null}
          </span>
        </div>

        <input
          type="range"
          className="slider mt-4"
          min={0}
          max={maxOverlap}
          step={10}
          value={value.chunkOverlap}
          disabled={disabled}
          aria-label="Chunk overlap in characters"
          aria-valuetext={`${value.chunkOverlap} characters`}
          onChange={(event) => applyOverlap(Number(event.target.value))}
        />
      </div>

      {autoAdjusted ? (
        <Alert tone="info">
          Overlap moved down to {formatNumber(value.chunkOverlap)} characters to stay below
          the new chunk size.
        </Alert>
      ) : null}

      {validationMessage ? <Alert tone="error">{validationMessage}</Alert> : null}
    </div>
  );
}
