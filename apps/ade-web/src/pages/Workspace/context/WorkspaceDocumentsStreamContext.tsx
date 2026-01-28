import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { type DocumentEventEntry } from "@/api/documents";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useDocumentsEventsStream } from "@/pages/Workspace/sections/Documents/shared/hooks/useDocumentsEventsStream";

type ConnectionState = "idle" | "connecting" | "open" | "closed";

type WorkspaceDocumentsStreamContextValue = {
  subscribe: (handler: (change: DocumentEventEntry) => void) => () => void;
  connectionState: ConnectionState;
};

const WorkspaceDocumentsStreamContext = createContext<WorkspaceDocumentsStreamContextValue | null>(null);

export function WorkspaceDocumentsStreamProvider({ children }: { readonly children: ReactNode }) {
  const { workspace } = useWorkspaceContext();
  const queryClient = useQueryClient();
  const listenersRef = useRef(new Set<(change: DocumentEventEntry) => void>());
  const reconnectPendingRef = useRef(false);

  const subscribe = useCallback((handler: (change: DocumentEventEntry) => void) => {
    listenersRef.current.add(handler);
    return () => {
      listenersRef.current.delete(handler);
    };
  }, []);

  const dispatchChange = useCallback((change: DocumentEventEntry) => {
    listenersRef.current.forEach((handler) => {
      handler(change);
    });
  }, []);

  const invalidateWorkspaceDocuments = useCallback(() => {
    if (!workspace.id) return;
    queryClient.invalidateQueries({ queryKey: ["documents", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["sidebar", "assigned-documents", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["documents-preview-row", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["documents-preview-details", workspace.id] });
  }, [queryClient, workspace.id]);

  useEffect(() => {
    if (!workspace.id) return;
    const handleFocus = () => invalidateWorkspaceDocuments();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        invalidateWorkspaceDocuments();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [invalidateWorkspaceDocuments, workspace.id]);

  const { connectionState } = useDocumentsEventsStream({
    workspaceId: workspace.id,
    enabled: Boolean(workspace.id),
    includeRows: true,
    onEvent: dispatchChange,
    onDisconnect: () => {
      reconnectPendingRef.current = true;
    },
    onReady: () => {
      if (reconnectPendingRef.current) {
        reconnectPendingRef.current = false;
        invalidateWorkspaceDocuments();
      }
    },
  });

  const value = useMemo(
    () => ({
      subscribe,
      connectionState,
    }),
    [connectionState, subscribe],
  );

  return (
    <WorkspaceDocumentsStreamContext.Provider value={value}>
      {children}
    </WorkspaceDocumentsStreamContext.Provider>
  );
}

export function useWorkspaceDocumentsChanges(handler: (change: DocumentEventEntry) => void) {
  const context = useContext(WorkspaceDocumentsStreamContext);
  if (!context) {
    throw new Error("useWorkspaceDocumentsChanges must be used within a WorkspaceDocumentsStreamProvider.");
  }
  const { subscribe } = context;
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => subscribe((change) => handlerRef.current(change)), [subscribe]);
}
