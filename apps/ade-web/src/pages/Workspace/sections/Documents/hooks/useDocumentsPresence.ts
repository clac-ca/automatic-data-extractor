import { useCallback, useEffect, useMemo, useRef } from "react";

import { usePresenceChannel } from "@hooks/presence";

const IDLE_TIMEOUT_MS = 120_000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"] as const;

type PresenceStatus = "active" | "idle";

type UseDocumentsPresenceOptions = {
  workspaceId?: string | null;
  enabled?: boolean;
};

export function useDocumentsPresence({ workspaceId, enabled = true }: UseDocumentsPresenceOptions) {
  const context = useMemo(() => ({ view: "list" }), []);
  const presence = usePresenceChannel({
    workspaceId: workspaceId ?? undefined,
    scope: "documents",
    context,
    enabled: enabled && Boolean(workspaceId),
  });
  const { connectionState, sendPresence } = presence;

  const statusRef = useRef<PresenceStatus>("active");
  const idleTimerRef = useRef<number | null>(null);

  const sendStatus = useCallback(
    (next: PresenceStatus) => {
      if (statusRef.current === next) return;
      statusRef.current = next;
      sendPresence({ status: next, page: "documents" });
    },
    [sendPresence],
  );

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      window.clearTimeout(idleTimerRef.current);
    }
    idleTimerRef.current = window.setTimeout(() => {
      sendStatus("idle");
    }, IDLE_TIMEOUT_MS);
  }, [sendStatus]);

  const markActive = useCallback(() => {
    if (document.hidden) return;
    sendStatus("active");
    resetIdleTimer();
  }, [resetIdleTimer, sendStatus]);

  useEffect(() => {
    if (!enabled || !workspaceId) return;
    if (connectionState !== "open") return;
    sendPresence({ status: statusRef.current, page: "documents" });
  }, [connectionState, enabled, sendPresence, workspaceId]);

  useEffect(() => {
    if (!enabled || !workspaceId) return;

    const handleVisibility = () => {
      if (document.hidden) {
        sendStatus("idle");
      } else {
        markActive();
      }
    };

    const handleActivity = () => {
      markActive();
    };

    markActive();

    ACTIVITY_EVENTS.forEach((event) => {
      window.addEventListener(event, handleActivity, { passive: true });
    });
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      ACTIVITY_EVENTS.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
      document.removeEventListener("visibilitychange", handleVisibility);
      if (idleTimerRef.current) {
        window.clearTimeout(idleTimerRef.current);
        idleTimerRef.current = null;
      }
    };
  }, [enabled, markActive, sendStatus, workspaceId]);

  return presence;
}
