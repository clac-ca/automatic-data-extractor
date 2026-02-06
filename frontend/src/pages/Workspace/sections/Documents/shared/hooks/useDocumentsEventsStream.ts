import { useEffect, useRef, useState } from "react";

import { documentsStreamUrl, type DocumentChangeNotification } from "@/api/documents";

type ConnectionState = "idle" | "connecting" | "open" | "closed";

type ReadyPayload = {
  lastId?: string | null;
};

export function useDocumentsEventsStream({
  workspaceId,
  enabled = true,
  onEvent,
  onDisconnect,
  onReady,
}: {
  workspaceId?: string | null;
  enabled?: boolean;
  onEvent: (change: DocumentChangeNotification) => void;
  onDisconnect?: () => void;
  onReady?: (lastId: string | null) => void;
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
    const connectionKey = workspaceId ?? null;
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

    const source = new EventSource(documentsStreamUrl(workspaceId), {
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
        const parsed = JSON.parse(event.data) as DocumentChangeNotification;
        if (!parsed.op) {
          parsed.op = event.type === "document.deleted" ? "delete" : "upsert";
        }
        if (!parsed.id && event.lastEventId) {
          parsed.id = event.lastEventId;
        }
        if (!parsed.documentId) return;
        handlersRef.current.onEvent(parsed);
      } catch {
        return;
      }
    };

    const handleReady = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      try {
        const payload = JSON.parse(event.data) as ReadyPayload;
        handlersRef.current.onReady?.(payload.lastId ?? null);
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
  }, [shouldConnect, workspaceId]);

  return { connectionState };
}
