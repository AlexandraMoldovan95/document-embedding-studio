/** Small formatting and validation helpers shared across components. */

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

export function formatDuration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export function getExtension(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? (parts.pop() ?? "").toLowerCase() : "";
}

/** The largest overlap allowed for a given chunk size: `min(2000, size - 1)`. */
export function effectiveMaxOverlap(chunkSize: number, ceiling = 2000): number {
  return Math.max(0, Math.min(ceiling, chunkSize - 1));
}

export interface ChunkValidation {
  valid: boolean;
  message: string | null;
}

/** The same rule the backend enforces: `0 <= overlap < chunk_size`. */
export function validateChunkSettings(
  chunkSize: number,
  overlap: number,
  min: number,
  max: number,
): ChunkValidation {
  if (!Number.isFinite(chunkSize) || !Number.isFinite(overlap)) {
    return { valid: false, message: "Enter a number for both chunk size and overlap." };
  }
  if (chunkSize < min || chunkSize > max) {
    return {
      valid: false,
      message: `Chunk size must be between ${min} and ${max} characters.`,
    };
  }
  if (overlap < 0) {
    return { valid: false, message: "Overlap cannot be negative." };
  }
  if (overlap >= chunkSize) {
    return {
      valid: false,
      message: `Overlap must be smaller than the chunk size. The most you can use here is ${effectiveMaxOverlap(chunkSize)} characters.`,
    };
  }
  return { valid: true, message: null };
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
