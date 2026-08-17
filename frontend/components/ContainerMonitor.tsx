"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "@/lib/api";
import type { ContainerSnapshot } from "@/lib/types";
import { Alert, EmptyState, IconDatabase, StatusChip } from "./Primitives";

type ConnectionState = "connecting" | "open" | "closed" | "error";

const RECONNECT_DELAY_MS = 3000;

export function ContainerMonitor() {
  const [containers, setContainers] = useState<ContainerSnapshot[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [serverError, setServerError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    const connect = () => {
      if (!mounted.current) return;
      setConnectionState("connecting");

      const socket = new WebSocket(`${WS_URL}/ws/containers`);
      socketRef.current = socket;

      socket.onopen = () => {
        if (mounted.current) setConnectionState("open");
      };

      socket.onmessage = (event) => {
        if (!mounted.current) return;
        try {
          const message = JSON.parse(event.data) as {
            ok: boolean;
            containers: ContainerSnapshot[];
            error: string | null;
          };
          setContainers(message.containers);
          setServerError(message.ok ? null : message.error);
        } catch {
          // Malformed frame — skip it, the next tick will self-correct.
        }
      };

      socket.onerror = () => {
        if (mounted.current) setConnectionState("error");
      };

      socket.onclose = () => {
        if (!mounted.current) return;
        setConnectionState("closed");
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    };

    connect();

    return () => {
      mounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      socketRef.current?.close();
    };
  }, []);

  return (
    <div>
      <div className="mb-4 flex items-center gap-2 text-xs text-ink-500">
        <span
          className={`h-2 w-2 rounded-full ${
            connectionState === "open"
              ? "bg-emerald-500"
              : connectionState === "connecting"
                ? "bg-amber-500"
                : "bg-red-500"
          }`}
        />
        {connectionState === "open"
          ? "Live"
          : connectionState === "connecting"
            ? "Connecting…"
            : "Reconnecting…"}
        <span className="text-ink-300">·</span>
        Only works when this app is started via <span className="font-mono">docker compose up</span>
      </div>

      {serverError ? (
        <div className="mb-4">
          <Alert tone="info">{serverError}</Alert>
        </div>
      ) : null}

      {containers.length === 0 && !serverError ? (
        <EmptyState
          icon={<IconDatabase width={28} height={28} />}
          title="Waiting for containers"
          description="No containers labeled for this app were found yet."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {containers.map((container) => (
            <ContainerCard key={container.id} container={container} />
          ))}
        </div>
      )}
    </div>
  );
}

function ContainerCard({ container }: { container: ContainerSnapshot }) {
  const memoryPercent =
    container.memory_limit_mb > 0
      ? Math.min(100, (container.memory_used_mb / container.memory_limit_mb) * 100)
      : 0;

  return (
    <div className="rounded-xl border border-ink-100 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink-800">{container.name}</p>
          <p className="truncate text-xs text-ink-400">
            {container.image} · {container.id}
          </p>
        </div>
        <StatusChip
          tone={container.status === "running" ? "success" : "neutral"}
          label={container.status}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-ink-400">CPU</p>
          <p className="text-base font-semibold text-ink-800">{container.cpu_percent}%</p>
        </div>
        <div>
          <p className="text-ink-400">Memory</p>
          <p className="text-base font-semibold text-ink-800">
            {container.memory_used_mb.toFixed(0)} MB
            <span className="ml-1 font-normal text-ink-400">
              / {container.memory_limit_mb.toFixed(0)} MB
            </span>
          </p>
        </div>
      </div>

      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-ink-50">
        <div
          className="h-full rounded-full bg-accent-500 transition-all"
          style={{ width: `${memoryPercent}%` }}
        />
      </div>
    </div>
  );
}
