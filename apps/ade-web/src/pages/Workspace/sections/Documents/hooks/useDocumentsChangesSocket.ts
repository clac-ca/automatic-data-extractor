import { useCallback, useEffect, useRef, useState } from "react";

import { documentsChangesSocketUrl, type DocumentChangeEntry } from "@api/documents";

const MAX_RETRY_MS = 30_000;

type ConnectionState = "idle" | "connecting" | "open" | "closed";

type ChangesMessage = {
  type: "changes";
  workspaceId?: string;
  fromCursor?: string;
  toCursor?: string;
  nextCursor?: string;
  items?: DocumentChangeEntry[];
};

type EventMessage = {
  type: "event";
  workspaceId?: string;
  change?: DocumentChangeEntry;
};

type ErrorMessage = {
  type: "error";
  code?: string;
  latestCursor?: string;
};

export function useDocumentsChangesSocket({
  workspaceId,
  cursor,
  enabled = true,
  onChanges,
  onEvent,
  onResyncRequired,
}: {
  workspaceId?: string | null;
  cursor?: string | null;
  enabled?: boolean;
  onChanges: (items: DocumentChangeEntry[], nextCursor: string | null) => void;
  onEvent: (change: DocumentChangeEntry) => void;
  onResyncRequired: (latestCursor: string | null) => void;
}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const cursorRef = useRef<string | null>(cursor ?? null);
  const handlersRef = useRef({ onChanges, onEvent, onResyncRequired });
  const cursorReady = Boolean(cursor);

  useEffect(() => {
    cursorRef.current = cursor ?? null;
  }, [cursor]);

  useEffect(() => {
    handlersRef.current = { onChanges, onEvent, onResyncRequired };
  }, [onChanges, onEvent, onResyncRequired]);

  const sendSubscribe = useCallback(() => {
    const socket = socketRef.current;
    const activeCursor = cursorRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN || !workspaceId || !activeCursor) {
      return;
    }
    socket.send(
      JSON.stringify({
        type: "subscribe",
        workspaceId,
        cursor: activeCursor,
      }),
    );
  }, [workspaceId]);

  useEffect(() => {
    if (!enabled || !workspaceId || !cursorReady) {
      socketRef.current?.close();
      socketRef.current = null;
      setConnectionState("idle");
      return;
    }

    let active = true;
    let reconnectTimer: number | null = null;

    const scheduleReconnect = () => {
      if (!active) return;
      const attempt = retryRef.current;
      const baseDelay = 1000;
      const delay = Math.min(MAX_RETRY_MS, baseDelay * 2 ** Math.min(attempt, 5));
      retryRef.current += 1;
      const jitter = Math.floor(delay * 0.15 * Math.random());
      reconnectTimer = window.setTimeout(connect, delay + jitter);
    };

    const handleMessage = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      let parsed: ChangesMessage | EventMessage | ErrorMessage;
      try {
        parsed = JSON.parse(event.data) as ChangesMessage | EventMessage | ErrorMessage;
      } catch {
        return;
      }

      const type = parsed.type;
      if (type === "changes") {
        const items = Array.isArray(parsed.items) ? parsed.items : [];
        handlersRef.current.onChanges(items, parsed.nextCursor ?? null);
        return;
      }
      if (type === "event" && parsed.change) {
        handlersRef.current.onEvent(parsed.change);
        return;
      }
      if (type === "error" && parsed.code === "resync_required") {
        handlersRef.current.onResyncRequired(parsed.latestCursor ?? null);
      }
    };

    const connect = () => {
      if (!active) return;
      setConnectionState("connecting");
      const socket = new WebSocket(documentsChangesSocketUrl(workspaceId));
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setConnectionState("open");
        sendSubscribe();
      };
      socket.onmessage = handleMessage;
      socket.onclose = () => {
        setConnectionState("closed");
        if (active) {
          scheduleReconnect();
        }
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socketRef.current?.close();
      socketRef.current = null;
      setConnectionState("idle");
    };
  }, [cursorReady, enabled, sendSubscribe, workspaceId]);

  return { connectionState };
}
