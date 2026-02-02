import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

import { usePresenceChannel } from "@/pages/Workspace/hooks/presence";
import type { PresenceConnectionState, PresenceParticipant } from "@/types/presence";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";

const IDLE_TIMEOUT_MS = 120_000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"] as const;

type PresenceStatus = "active" | "idle";

type WorkspacePresenceContextValue = {
  participants: PresenceParticipant[];
  connectionState: PresenceConnectionState;
  clientId: string | null;
  setPresence: (payload: Record<string, unknown>) => void;
  sendSelection: (payload: Record<string, unknown>) => void;
  sendEditing: (payload: Record<string, unknown>) => void;
};

const WorkspacePresenceContext = createContext<WorkspacePresenceContextValue | null>(null);

export function WorkspacePresenceProvider({ children }: { readonly children: ReactNode }) {
  const { workspace } = useWorkspaceContext();
  const enabled = Boolean(workspace.id);

  const presence = usePresenceChannel({
    workspaceId: workspace.id,
    scope: "workspace",
    enabled,
  });

  const presencePayloadRef = useRef<Record<string, unknown>>({});
  const statusRef = useRef<PresenceStatus>("active");
  const idleTimerRef = useRef<number | null>(null);

  useEffect(() => {
    presencePayloadRef.current = {};
    statusRef.current = "active";
  }, [workspace.id]);

  const sendPresence = useCallback(() => {
    const payload = {
      ...presencePayloadRef.current,
      status: statusRef.current,
    };
    presencePayloadRef.current = payload;
    presence.sendPresence(payload);
  }, [presence.sendPresence]);

  const setPresence = useCallback(
    (payload: Record<string, unknown>) => {
      presencePayloadRef.current = { ...presencePayloadRef.current, ...payload };
      sendPresence();
    },
    [sendPresence],
  );

  const sendStatus = useCallback(
    (next: PresenceStatus) => {
      if (statusRef.current === next) return;
      statusRef.current = next;
      sendPresence();
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
    if (!enabled || !workspace.id) return;
    if (presence.connectionState !== "open") return;
    sendPresence();
  }, [enabled, presence.connectionState, sendPresence, workspace.id]);

  useEffect(() => {
    if (!enabled || !workspace.id) return;

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
  }, [enabled, markActive, sendStatus, workspace.id]);

  const value = useMemo(
    () => ({
      participants: presence.participants,
      connectionState: presence.connectionState,
      clientId: presence.clientId ?? null,
      setPresence,
      sendSelection: presence.sendSelection,
      sendEditing: presence.sendEditing,
    }),
    [
      presence.clientId,
      presence.connectionState,
      presence.participants,
      presence.sendEditing,
      presence.sendSelection,
      setPresence,
    ],
  );

  return <WorkspacePresenceContext.Provider value={value}>{children}</WorkspacePresenceContext.Provider>;
}

export function useWorkspacePresence() {
  const context = useContext(WorkspacePresenceContext);
  if (!context) {
    throw new Error("useWorkspacePresence must be used within a WorkspacePresenceProvider.");
  }
  return context;
}
