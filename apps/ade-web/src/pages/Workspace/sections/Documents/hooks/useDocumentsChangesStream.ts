import { useEffect, useRef, useState } from "react";

import { documentsChangesStreamUrl, type DocumentChangeEntry } from "@/api/documents";

type ConnectionState = "idle" | "connecting" | "open" | "closed";

type ResyncPayload = {
  code?: string;
  latestCursor?: string;
  oldestCursor?: string;
};

type ReadyPayload = {
  cursor?: string | number | null;
};

export function useDocumentsChangesStream({
  workspaceId,
  cursor,
  enabled = true,
  includeRows = false,
  onEvent,
  onResyncRequired,
  onReady,
}: {
  workspaceId?: string | null;
  cursor?: string | null;
  enabled?: boolean;
  includeRows?: boolean;
  onEvent: (change: DocumentChangeEntry) => void;
  onResyncRequired: (latestCursor: string | null, oldestCursor: string | null) => void;
  onReady?: (cursor: string | null) => void;
}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const sourceRef = useRef<EventSource | null>(null);
  const cursorRef = useRef<string | null>(null);
  const connectionKeyRef = useRef<string | null>(null);
  const handlersRef = useRef({ onEvent, onResyncRequired, onReady });

  useEffect(() => {
    handlersRef.current = { onEvent, onResyncRequired, onReady };
  }, [onEvent, onReady, onResyncRequired]);

  const shouldConnect = Boolean(enabled && workspaceId && cursor);

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

    const initialCursor = cursorRef.current ?? cursor;
    if (!initialCursor) {
      setConnectionState("idle");
      return;
    }

    let active = true;
    setConnectionState("connecting");

    const source = new EventSource(
      documentsChangesStreamUrl(workspaceId, initialCursor, { includeRows }),
      {
        withCredentials: true,
      },
    );
    sourceRef.current = source;

    const handleOpen = () => {
      if (!active) return;
      setConnectionState("open");
    };

    const handleChange = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      try {
        const parsed = JSON.parse(event.data) as DocumentChangeEntry;
        if (!parsed.cursor && event.lastEventId) {
          parsed.cursor = event.lastEventId;
        }
        if (parsed.cursor) {
          const nextCursor = String(parsed.cursor);
          const currentCursor = cursorRef.current;
          if (currentCursor) {
            const currentValue = Number(currentCursor);
            const nextValue = Number(nextCursor);
            if (!Number.isNaN(currentValue) && !Number.isNaN(nextValue) && nextValue <= currentValue) {
              return;
            }
          }
          cursorRef.current = nextCursor;
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
        if (nextCursor) {
          cursorRef.current = nextCursor;
        }
        handlersRef.current.onReady?.(nextCursor);
      } catch {
        return;
      }
    };

    const handleErrorEvent = (event: Event) => {
      if ("data" in event && typeof (event as MessageEvent).data === "string") {
        try {
          const payload = JSON.parse((event as MessageEvent).data) as ResyncPayload;
          if (payload.code === "resync_required") {
            handlersRef.current.onResyncRequired(payload.latestCursor ?? null, payload.oldestCursor ?? null);
            source.close();
            if (active) {
              setConnectionState("closed");
            }
          }
        } catch {
          return;
        }
        return;
      }
      if (!active) return;
      setConnectionState("closed");
    };

    source.addEventListener("open", handleOpen);
    source.addEventListener("ready", handleReady);
    source.addEventListener("document.changed", handleChange);
    source.addEventListener("document.deleted", handleChange);
    source.addEventListener("error", handleErrorEvent);

    return () => {
      active = false;
      source.close();
      sourceRef.current = null;
      setConnectionState("idle");
    };
  }, [includeRows, shouldConnect, workspaceId]);

  useEffect(() => {
    if (!cursor) return;
    cursorRef.current = cursor;
  }, [cursor]);

  return { connectionState };
}
