import { useEffect, useRef, useState } from "react";

import { documentsEventsStreamUrl, type DocumentEventEntry } from "@/api/documents";

type ConnectionState = "idle" | "connecting" | "open" | "closed";

type ReadyPayload = {
  cursor?: string | number | null;
};

export function useDocumentsEventsStream({
  workspaceId,
  enabled = true,
  includeRows = false,
  onEvent,
  onDisconnect,
  onReady,
}: {
  workspaceId?: string | null;
  enabled?: boolean;
  includeRows?: boolean;
  onEvent: (change: DocumentEventEntry) => void;
  onDisconnect?: () => void;
  onReady?: (cursor: string | null) => void;
}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const sourceRef = useRef<EventSource | null>(null);
  const connectionKeyRef = useRef<string | null>(null);
  const handlersRef = useRef({ onEvent, onDisconnect, onReady });

  useEffect(() => {
    handlersRef.current = { onEvent, onDisconnect, onReady };
  }, [onEvent, onDisconnect, onReady]);

  const shouldConnect = Boolean(enabled && workspaceId);

  useEffect(() => {
    const connectionKey = workspaceId ? `${workspaceId}:${includeRows}` : null;
    if (!shouldConnect || !workspaceId) {
      sourceRef.current?.close();
      sourceRef.current = null;
      connectionKeyRef.current = null;
      setConnectionState("idle");
      return;
    }

    if (sourceRef.current && connectionKeyRef.current === connectionKey) {
      return;
    }

    sourceRef.current?.close();
    sourceRef.current = null;
    connectionKeyRef.current = connectionKey;

    let active = true;
    setConnectionState("connecting");

    const source = new EventSource(documentsEventsStreamUrl(workspaceId, { includeRows }), {
      withCredentials: true,
    });
    sourceRef.current = source;

    const handleOpen = () => {
      if (!active) return;
      setConnectionState("open");
    };

    const handleEvent = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      try {
        const parsed = JSON.parse(event.data) as DocumentEventEntry;
        if (!parsed.cursor && event.lastEventId) {
          parsed.cursor = event.lastEventId;
        }
        handlersRef.current.onEvent(parsed);
      } catch {
        return;
      }
    };

    const handleReady = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      try {
        const payload = JSON.parse(event.data) as ReadyPayload;
        const nextCursor =
          typeof payload.cursor === "number" ? String(payload.cursor) : payload.cursor ?? null;
        handlersRef.current.onReady?.(nextCursor);
      } catch {
        return;
      }
    };

    const handleErrorEvent = () => {
      if (!active) return;
      setConnectionState("closed");
      handlersRef.current.onDisconnect?.();
    };

    source.addEventListener("open", handleOpen);
    source.addEventListener("ready", handleReady);
    source.addEventListener("document.changed", handleEvent);
    source.addEventListener("document.deleted", handleEvent);
    source.addEventListener("error", handleErrorEvent);

    return () => {
      active = false;
      source.close();
      sourceRef.current = null;
      setConnectionState("idle");
    };
  }, [includeRows, shouldConnect, workspaceId]);

  return { connectionState };
}
