"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { ChunkPreview } from "@/components/ChunkPreview";
import { ChunkSettings, type ChunkSettingsValue } from "@/components/ChunkSettings";
import { CollectionSelector } from "@/components/CollectionSelector";
import { ContainerMonitor } from "@/components/ContainerMonitor";
import { FileDropzone } from "@/components/FileDropzone";
import { FileList } from "@/components/FileList";
import {
  Alert,
  Button,
  IconSpark,
  Panel,
  SectionHeading,
  Spinner,
} from "@/components/Primitives";
import { ProcessingStatus, type ProcessingState } from "@/components/ProcessingStatus";
import { SearchTester } from "@/components/SearchTester";
import {
  ApiError,
  createCollection as createCollectionRequest,
  deleteCollection as deleteCollectionRequest,
  fetchChunks,
  fetchConfig,
  ingestFile,
  listCollections,
} from "@/lib/api";
import { getExtension, validateChunkSettings } from "@/lib/format";
import type {
  ChunkPreview as Chunk,
  CollectionInfo,
  FileError,
  QueuedFile,
  RunSummary,
  StudioConfig,
} from "@/lib/types";

const FALLBACK_CONFIG: StudioConfig = {
  default_collection: "documents",
  embedding_model: "all-MiniLM-L6-v2",
  embedding_provider: "sentence-transformers",
  supported_extensions: ["docx", "md", "pdf", "txt"],
  max_file_size_mb: 50,
  max_files_per_request: 25,
  min_chunk_size: 100,
  max_chunk_size: 10000,
  max_overlap: 2000,
  default_chunk_size: 1000,
  default_chunk_overlap: 200,
};

const IDLE_PROGRESS: ProcessingState = {
  completed: 0,
  total: 0,
  currentFile: null,
  uploadPercent: 0,
};

export default function Home() {
  const [config, setConfig] = useState<StudioConfig>(FALLBACK_CONFIG);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const [files, setFiles] = useState<QueuedFile[]>([]);
  const [settings, setSettings] = useState<ChunkSettingsValue>({
    chunkSize: 1000,
    chunkOverlap: 200,
  });

  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [collection, setCollection] = useState("documents");
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);

  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState<ProcessingState>(IDLE_PROGRESS);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);

  const [previewChunks, setPreviewChunks] = useState<Chunk[]>([]);
  const [previewTotal, setPreviewTotal] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  /* ---------------------------------------------------------------- setup */

  const refreshCollections = useCallback(async (): Promise<CollectionInfo[]> => {
    const response = await listCollections();
    setCollections(response.collections);
    return response.collections;
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setCollectionsLoading(true);
      try {
        const loadedConfig = await fetchConfig();
        if (cancelled) return;
        setConfig(loadedConfig);
        setSettings({
          chunkSize: loadedConfig.default_chunk_size,
          chunkOverlap: loadedConfig.default_chunk_overlap,
        });
        setCollection(loadedConfig.default_collection);
        setConnectionError(null);

        const available = await refreshCollections();
        if (cancelled) return;
        // Prefer the default collection if it already exists, else the first one.
        const preferred =
          available.find((item) => item.name === loadedConfig.default_collection)?.name ??
          available[0]?.name ??
          loadedConfig.default_collection;
        setCollection(preferred);
        setCollectionsError(null);
      } catch (error) {
        if (cancelled) return;
        setConnectionError(
          error instanceof ApiError
            ? error.message
            : "The backend could not be reached. Start it, then reload this page.",
        );
      } finally {
        if (!cancelled) setCollectionsLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [refreshCollections]);

  /* Load stored chunks whenever the selected collection changes. */
  useEffect(() => {
    if (!collection || connectionError) return;
    let cancelled = false;

    const load = async () => {
      setPreviewLoading(true);
      try {
        const response = await fetchChunks(collection, 50, 0);
        if (cancelled) return;
        setPreviewChunks(response.chunks);
        setPreviewTotal(response.total);
      } catch {
        if (cancelled) return;
        setPreviewChunks([]);
        setPreviewTotal(0);
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [collection, connectionError]);

  /* ------------------------------------------------------------- validation */

  const validation = useMemo(
    () =>
      validateChunkSettings(
        settings.chunkSize,
        settings.chunkOverlap,
        config.min_chunk_size,
        config.max_chunk_size,
      ),
    [settings, config.min_chunk_size, config.max_chunk_size],
  );

  const readyFiles = files.filter((file) => file.status === "ready");
  const canProcess =
    readyFiles.length > 0 && validation.valid && !isProcessing && !connectionError;

  const selectedChunkCount =
    collections.find((item) => item.name === collection)?.chunk_count ?? 0;

  /* ------------------------------------------------------------------ files */

  const addFiles = useCallback(
    (incoming: File[]) => {
      setFiles((existing) => {
        const room = config.max_files_per_request - existing.length;
        const accepted = incoming.slice(0, Math.max(0, room));
        const queued = accepted.map<QueuedFile>((file) => {
          const extension = getExtension(file.name);
          const supported = config.supported_extensions.includes(extension);
          const tooBig = file.size > config.max_file_size_mb * 1024 * 1024;
          return {
            id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
            file,
            name: file.name,
            extension,
            size: file.size,
            status: supported && !tooBig ? "ready" : "error",
            uploadProgress: 0,
            chunksCreated: 0,
            characters: 0,
            pages: null,
            error: !supported
              ? `.${extension || "?"} files are not supported. Use ${config.supported_extensions.map((item) => `.${item}`).join(", ")}.`
              : tooBig
                ? `This file is larger than the ${config.max_file_size_mb} MB limit.`
                : null,
          };
        });

        // Same name and size already queued: skip the duplicate.
        const seen = new Set(existing.map((file) => `${file.name}:${file.size}`));
        return [...existing, ...queued.filter((file) => !seen.has(`${file.name}:${file.size}`))];
      });
    },
    [config],
  );

  const removeFile = (id: string) =>
    setFiles((existing) => existing.filter((file) => file.id !== id));

  const clearFiles = () => setFiles([]);

  const patchFile = (id: string, patch: Partial<QueuedFile>) =>
    setFiles((existing) =>
      existing.map((file) => (file.id === id ? { ...file, ...patch } : file)),
    );

  /* ------------------------------------------------------------ processing */

  const process = async () => {
    // Only files that passed client-side checks and are not yet indexed.
    const processable = files.filter((file) => file.status === "ready");
    if (processable.length === 0 || !validation.valid) return;

    const controller = new AbortController();
    abortRef.current = controller;

    setIsProcessing(true);
    setFatalError(null);
    setSummary(null);
    setProgress({
      completed: 0,
      total: processable.length,
      currentFile: null,
      uploadPercent: 0,
    });

    const startedAt = performance.now();
    const collected: Chunk[] = [];
    const errors: FileError[] = [];
    let documentsProcessed = 0;
    let charactersExtracted = 0;
    let chunksCreated = 0;
    let embeddingsCreated = 0;
    let embeddingModel = "";

    for (const [position, queued] of processable.entries()) {
      setProgress({
        completed: position,
        total: processable.length,
        currentFile: queued.name,
        uploadPercent: 0,
      });
      patchFile(queued.id, { status: "uploading", uploadProgress: 0, error: null });

      try {
        const response = await ingestFile({
          file: queued.file,
          chunkSize: settings.chunkSize,
          chunkOverlap: settings.chunkOverlap,
          collectionName: collection,
          signal: controller.signal,
          onUploadProgress: (percent) => {
            setProgress((current) => ({ ...current, uploadPercent: percent }));
            patchFile(queued.id, { uploadProgress: percent });
            // Once the bytes are sent, the server starts with extraction.
            if (percent >= 100) patchFile(queued.id, { status: "extracting" });
          },
        });

        const result = response.files[0];
        embeddingModel = response.embedding_model || embeddingModel;

        if (result && result.status === "indexed") {
          documentsProcessed += 1;
          charactersExtracted += response.characters_extracted;
          chunksCreated += response.chunks_created;
          embeddingsCreated += response.embeddings_created;
          collected.push(...response.chunks);
          patchFile(queued.id, {
            status: "indexed",
            uploadProgress: 100,
            chunksCreated: result.chunks_created,
            characters: result.characters,
            pages: result.pages,
            error: null,
          });
        } else {
          const message = result?.error ?? "This file could not be processed.";
          errors.push({
            filename: queued.name,
            code: result?.error_code ?? "processing_failed",
            message,
          });
          patchFile(queued.id, { status: "error", error: message });
        }
      } catch (error) {
        if (error instanceof ApiError && error.code === "aborted") {
          patchFile(queued.id, { status: "ready", uploadProgress: 0 });
          break;
        }
        const message =
          error instanceof ApiError ? error.message : "This file could not be processed.";
        errors.push({ filename: queued.name, code: "request_failed", message });
        patchFile(queued.id, { status: "error", error: message });
        // A failure here is per file; the loop continues with the next one.
      }

      setProgress((current) => ({ ...current, completed: position + 1, uploadPercent: 0 }));
    }

    setSummary({
      collection,
      documentsProcessed,
      documentsFailed: errors.length,
      charactersExtracted,
      chunksCreated,
      embeddingsCreated,
      durationSeconds: (performance.now() - startedAt) / 1000,
      embeddingModel,
      errors,
    });

    if (collected.length > 0) {
      setPreviewChunks(collected);
      setPreviewTotal(collected.length);
    }

    try {
      await refreshCollections();
    } catch {
      // Stats are cosmetic here; ingestion already succeeded.
    }

    setIsProcessing(false);
    setProgress(IDLE_PROGRESS);
    abortRef.current = null;
  };

  /* ---------------------------------------------------------- collections */

  const handleCreateCollection = async (name: string) => {
    const created = await createCollectionRequest(name);
    await refreshCollections();
    setCollection(created.name);
    setCollectionsError(null);
  };

  const handleDeleteCollection = async (name: string) => {
    try {
      await deleteCollectionRequest(name);
      const remaining = await refreshCollections();
      setCollection(remaining[0]?.name ?? config.default_collection);
      setPreviewChunks([]);
      setPreviewTotal(0);
      setSummary(null);
      setCollectionsError(null);
    } catch (error) {
      setCollectionsError(
        error instanceof ApiError ? error.message : "The collection was not deleted.",
      );
    }
  };

  /* --------------------------------------------------------------- render */

  return (
    <div className="min-h-screen">
      <header className="border-b border-ink-200/60 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-5 sm:px-6">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-600 text-white">
            <IconSpark width={18} height={18} />
          </span>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-ink-900">
              Document Embedding Studio
            </h1>
            <p className="text-xs text-ink-500">Chunk · Embed · Store</p>
          </div>
          <p className="ml-auto hidden text-right text-xs text-ink-500 sm:block">
            <span className="font-mono">{config.embedding_model}</span>
            <br />
            ChromaDB · local storage
          </p>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {connectionError ? (
          <Alert tone="error" title="Backend unavailable">
            {connectionError}
          </Alert>
        ) : null}

        {/* Upload + settings ------------------------------------------- */}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Panel>
            <SectionHeading
              title="Documents"
              hint="PDF, DOCX, Markdown, and plain text."
            />
            <FileDropzone
              onFilesAdded={addFiles}
              supportedExtensions={config.supported_extensions}
              maxFileSizeMb={config.max_file_size_mb}
              disabled={isProcessing}
            />
            <FileList
              files={files}
              onRemove={removeFile}
              onClearAll={clearFiles}
              isProcessing={isProcessing}
            />
          </Panel>

          <Panel>
            <SectionHeading
              title="Chunk settings"
              hint="Applied when you process. Existing chunks keep the settings they were made with."
            />
            <ChunkSettings
              value={settings}
              onChange={setSettings}
              minChunkSize={config.min_chunk_size}
              maxChunkSize={config.max_chunk_size}
              overlapCeiling={config.max_overlap}
              validationMessage={validation.message}
              disabled={isProcessing}
            />
            <hr className="my-7 border-ink-100" />
            <CollectionSelector
              collections={collections}
              selected={collection}
              loading={collectionsLoading}
              error={collectionsError}
              disabled={isProcessing}
              onSelect={setCollection}
              onCreate={handleCreateCollection}
              onDelete={handleDeleteCollection}
            />
          </Panel>
        </div>

        {/* Process ------------------------------------------------------ */}
        <Panel className="flex flex-col items-center gap-3 py-5">
          <Button
            variant="primary"
            size="lg"
            className="w-full sm:w-auto sm:min-w-[280px]"
            onClick={() => void process()}
            disabled={!canProcess}
          >
            {isProcessing ? <Spinner /> : null}
            {isProcessing ? "Processing…" : "Process & embed"}
          </Button>
          <p className="text-center text-xs text-ink-500">
            {!validation.valid
              ? validation.message
              : readyFiles.length === 0
                ? "Add a document to get started."
                : `${readyFiles.length} ${readyFiles.length === 1 ? "file" : "files"} · ${settings.chunkSize} characters per chunk · ${settings.chunkOverlap} overlap · into ${collection}`}
          </p>
          {isProcessing ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => abortRef.current?.abort()}
            >
              Cancel
            </Button>
          ) : null}
        </Panel>

        {/* Results ------------------------------------------------------ */}
        <Panel>
          <SectionHeading title="Processing" hint="Statistics from your most recent run." />
          <ProcessingStatus
            isProcessing={isProcessing}
            progress={progress}
            summary={summary}
            fatalError={fatalError}
          />
        </Panel>

        {/* Chunk preview ------------------------------------------------ */}
        <Panel>
          <SectionHeading
            title="Chunk preview"
            hint="Exactly what was stored, one chunk at a time."
          />
          <ChunkPreview
            chunks={previewChunks}
            loading={previewLoading}
            totalInCollection={previewTotal}
            emptyMessage={`Nothing indexed in "${collection}" yet. Process a document to see how it was split.`}
          />
        </Panel>

        {/* Search ------------------------------------------------------- */}
        <Panel>
          <SectionHeading
            title="Test semantic search"
            hint="Query the vectors you just stored — fully local, nothing leaves this machine."
          />
          <SearchTester collectionName={collection} chunkCount={selectedChunkCount} />
        </Panel>

        {/* Chat (BYOK) --------------------------------------------------- */}
        <Panel>
          <SectionHeading
            title="Ask the assistant"
            hint="Bring your own API key — the assistant answers in plain language, grounded in this collection."
          />
          <ChatPanel collectionName={collection} chunkCount={selectedChunkCount} />
        </Panel>

        {/* Container status (live via WebSocket) -------------------------- */}
        <Panel>
          <SectionHeading
            title="Container status"
            hint="Live CPU and memory for this app's own Docker containers, pushed over a WebSocket."
          />
          <ContainerMonitor />
        </Panel>

        <p className="pb-4 text-center text-xs text-ink-400">
          Ingestion, chunking, embedding, and search run locally in ChromaDB. Only the "Ask the
          assistant" panel sends data out — to whichever provider you choose, using your own key.
        </p>
      </main>
    </div>
  );
}
