import { useEffect, useRef, useState } from "react";

import { documentsChangesStreamUrl, type DocumentChangeEntry } from "@api/documents";

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
  onEvent,
  onResyncRequired,
  onReady,
}: {
  workspaceId?: string | null;
  cursor?: string | null;
  enabled?: boolean;
  onEvent: (change: DocumentChangeEntry) => void;
  onResyncRequired: (latestCursor: string | null, oldestCursor: string | null) => void;
  onReady?: (cursor: string | null) => void;
}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const sourceRef = useRef<EventSource | null>(null);
  const handlersRef = useRef({ onEvent, onResyncRequired, onReady });

  useEffect(() => {
    handlersRef.current = { onEvent, onResyncRequired, onReady };
  }, [onEvent, onReady, onResyncRequired]);

  useEffect(() => {
    if (!enabled || !workspaceId || !cursor) {
      sourceRef.current?.close();
      sourceRef.current = null;
      setConnectionState("idle");
      return;
    }

    let active = true;
    setConnectionState("connecting");

    const source = new EventSource(documentsChangesStreamUrl(workspaceId, cursor), {
      withCredentials: true,
    });
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
  }, [cursor, enabled, workspaceId]);

  return { connectionState };
}
