import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { presenceSocketUrl } from "./client";
import type { PresenceConnectionState, PresenceContext, PresenceParticipant } from "./types";

const DEFAULT_HEARTBEAT_MS = 15_000;
const MAX_RETRY_MS = 30_000;

export type UsePresenceChannelOptions = {
  workspaceId?: string | null;
  scope: string;
  context?: PresenceContext;
  enabled?: boolean;
};

function createClientId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `client-${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36)}`;
}

function normalizeContext(context?: PresenceContext) {
  if (!context) return {};
  const normalized: PresenceContext = {};
  for (const key of Object.keys(context).sort()) {
    normalized[key] = context[key];
  }
  return normalized;
}

export function usePresenceChannel({
  workspaceId,
  scope,
  context,
  enabled = true,
}: UsePresenceChannelOptions) {
  const [participants, setParticipants] = useState<PresenceParticipant[]>([]);
  const [connectionState, setConnectionState] = useState<PresenceConnectionState>("idle");
  const [clientId, setClientId] = useState(() => createClientId());

  const socketRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const retryRef = useRef(0);
  const heartbeatIntervalRef = useRef(DEFAULT_HEARTBEAT_MS);
  const lastHelloRef = useRef<string | null>(null);

  const normalizedContext = useMemo(() => normalizeContext(context), [context]);
  const contextKey = useMemo(() => JSON.stringify(normalizedContext), [normalizedContext]);

  useEffect(() => {
    setClientId(createClientId());
  }, [workspaceId]);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      window.clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((payload: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify(payload));
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = window.setInterval(() => {
      sendMessage({ type: "heartbeat" });
    }, heartbeatIntervalRef.current);
  }, [sendMessage, stopHeartbeat]);

  const sendHello = useCallback(() => {
    if (!workspaceId) return;
    const payload = {
      type: "hello",
      client_id: clientId,
      scope,
      context: normalizedContext,
    };
    const encoded = JSON.stringify(payload);
    if (encoded === lastHelloRef.current) return;
    lastHelloRef.current = encoded;
    sendMessage(payload);
  }, [clientId, normalizedContext, scope, sendMessage, workspaceId]);

  useEffect(() => {
    if (!enabled || !workspaceId) {
      stopHeartbeat();
      socketRef.current?.close();
      socketRef.current = null;
      setParticipants([]);
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
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(event.data) as Record<string, unknown>;
      } catch {
        return;
      }

      const messageType = typeof parsed.type === "string" ? parsed.type : "";
      if (!messageType) return;

      if (messageType === "hello") {
        if (typeof parsed.client_id === "string") {
          setClientId(parsed.client_id);
        }
        if (typeof parsed.heartbeat_interval === "number") {
          heartbeatIntervalRef.current = Math.max(5000, parsed.heartbeat_interval * 1000);
          if (socketRef.current?.readyState === WebSocket.OPEN) {
            startHeartbeat();
          }
        }
        return;
      }

      if (messageType === "snapshot") {
        const next = Array.isArray(parsed.participants) ? (parsed.participants as PresenceParticipant[]) : [];
        setParticipants(next);
        return;
      }

      if (messageType === "join") {
        const participant = parsed.participant as PresenceParticipant | undefined;
        if (!participant || typeof participant.client_id !== "string") return;
        setParticipants((prev) => {
          const next = prev.filter((item) => item.client_id !== participant.client_id);
          next.push(participant);
          return next;
        });
        return;
      }

      if (messageType === "leave") {
        const departingId = parsed.client_id;
        if (typeof departingId !== "string") return;
        setParticipants((prev) => prev.filter((item) => item.client_id !== departingId));
        return;
      }

      if (messageType === "presence" || messageType === "selection" || messageType === "editing") {
        const targetId = parsed.client_id;
        if (typeof targetId !== "string") return;
        const { type: _ignore, client_id: _id, ...payload } = parsed;
        setParticipants((prev) =>
          prev.map((participant) => {
            if (participant.client_id !== targetId) return participant;
            if (messageType === "presence") {
              const status = typeof parsed.status === "string" ? parsed.status : participant.status;
              return { ...participant, presence: payload, status };
            }
            if (messageType === "selection") {
              return { ...participant, selection: payload };
            }
            return { ...participant, editing: payload };
          }),
        );
      }
    };

    const connect = () => {
      if (!active) return;
      setConnectionState("connecting");
      const socket = new WebSocket(presenceSocketUrl(workspaceId));
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setConnectionState("open");
        lastHelloRef.current = null;
        startHeartbeat();
        sendHello();
      };

      socket.onmessage = handleMessage;

      socket.onclose = () => {
        stopHeartbeat();
        setConnectionState("closed");
        if (active) {
          setParticipants([]);
          scheduleReconnect();
        }
      };

      socket.onerror = () => {
        // rely on close to trigger reconnect
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      stopHeartbeat();
      socketRef.current?.close();
      socketRef.current = null;
      setParticipants([]);
      setConnectionState("idle");
    };
  }, [enabled, sendHello, startHeartbeat, stopHeartbeat, workspaceId]);

  useEffect(() => {
    if (!enabled || !workspaceId) return;
    sendHello();
  }, [contextKey, enabled, scope, sendHello, workspaceId]);

  const sendPresence = useCallback(
    (payload: Record<string, unknown>) => {
      sendMessage({ type: "presence", ...payload });
    },
    [sendMessage],
  );

  const sendSelection = useCallback(
    (payload: Record<string, unknown>) => {
      sendMessage({ type: "selection", ...payload });
    },
    [sendMessage],
  );

  const sendEditing = useCallback(
    (payload: Record<string, unknown>) => {
      sendMessage({ type: "editing", ...payload });
    },
    [sendMessage],
  );

  return {
    participants,
    connectionState,
    clientId,
    sendPresence,
    sendSelection,
    sendEditing,
  };
}
