/** Typed client for the FastAPI backend. */

import type {
  ChatResponse,
  ChunkListResponse,
  CollectionInfo,
  CollectionListResponse,
  CollectionStats,
  DeleteCollectionResponse,
  IngestResponse,
  LlmProvider,
  SearchResponse,
  StudioConfig,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Same host as API_URL, just with the ws(s):// scheme, for the live container panel. */
export const WS_URL = API_URL.replace(/^http/, "ws");

/** An error the backend described in its `{ code, message }` envelope. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code = "error", status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

interface ErrorEnvelope {
  code?: string;
  message?: string;
  detail?: string;
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return typeof value === "object" && value !== null;
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = "error";
  let message = `The server responded with ${response.status}.`;
  try {
    const body: unknown = await response.json();
    if (isErrorEnvelope(body)) {
      message = body.message ?? body.detail ?? message;
      code = body.code ?? code;
    }
  } catch {
    // A non-JSON body (a proxy error page, say) keeps the generic message.
  }
  return new ApiError(message, code, response.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(
      "The backend is not reachable. Start it, then try again.",
      "network_error",
    );
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export function fetchConfig(): Promise<StudioConfig> {
  return request<StudioConfig>("/api/config");
}

export function listCollections(): Promise<CollectionListResponse> {
  return request<CollectionListResponse>("/api/collections");
}

export function createCollection(name: string): Promise<CollectionInfo> {
  return request<CollectionInfo>("/api/collections", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function deleteCollection(name: string): Promise<DeleteCollectionResponse> {
  return request<DeleteCollectionResponse>(`/api/collections/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export function fetchCollectionStats(name: string): Promise<CollectionStats> {
  return request<CollectionStats>(`/api/collections/${encodeURIComponent(name)}/stats`);
}

export function fetchChunks(
  name: string,
  limit = 50,
  offset = 0,
): Promise<ChunkListResponse> {
  return request<ChunkListResponse>(
    `/api/collections/${encodeURIComponent(name)}/chunks?limit=${limit}&offset=${offset}`,
  );
}

export function search(params: {
  query: string;
  collection_name: string;
  top_k: number;
  filename?: string | null;
}): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface AskParams {
  query: string;
  collectionName: string;
  topK: number;
  provider: LlmProvider;
  apiKey: string;
  model?: string;
  history?: { role: "user" | "assistant"; content: string }[];
}

/**
 * BYOK: apiKey travels only in this one request body, straight from the
 * browser to our backend to the chosen provider. It is never written to
 * localStorage by this function, never logged, never stored server-side.
 */
export function askChat(params: AskParams): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      query: params.query,
      collection_name: params.collectionName,
      top_k: params.topK,
      provider: params.provider,
      api_key: params.apiKey,
      model: params.model || undefined,
      history: params.history ?? [],
    }),
  });
}

export interface IngestParams {
  file: File;
  chunkSize: number;
  chunkOverlap: number;
  collectionName: string;
  /** Fired with 0–100 as the bytes actually leave the browser. */
  onUploadProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

/**
 * Send one file to `/api/ingest`.
 *
 * XHR rather than fetch, because it reports genuine upload progress; the UI
 * shows a real number instead of an invented one.
 */
export function ingestFile({
  file,
  chunkSize,
  chunkOverlap,
  collectionName,
  onUploadProgress,
  signal,
}: IngestParams): Promise<IngestResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("files", file, file.name);
    form.append("chunk_size", String(chunkSize));
    form.append("chunk_overlap", String(chunkOverlap));
    form.append("collection_name", collectionName);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/ingest`);
    xhr.responseType = "text";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onUploadProgress) {
        onUploadProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      let parsed: unknown = null;
      try {
        parsed = JSON.parse(xhr.responseText) as unknown;
      } catch {
        reject(new ApiError("The server sent a response we could not read.", "bad_response"));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(parsed as IngestResponse);
        return;
      }
      const envelope = isErrorEnvelope(parsed) ? parsed : {};
      reject(
        new ApiError(
          envelope.message ?? envelope.detail ?? "This file could not be processed.",
          envelope.code ?? "error",
          xhr.status,
        ),
      );
    });

    xhr.addEventListener("error", () => {
      reject(new ApiError("The backend is not reachable. Start it, then try again.", "network_error"));
    });
    xhr.addEventListener("abort", () => {
      reject(new ApiError("Processing was cancelled.", "aborted"));
    });

    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}
