import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  DocumentChangesResyncError,
  fetchWorkspaceDocumentChanges,
  fetchWorkspaceDocuments,
  type DocumentChangeEntry,
} from "@/api/documents";
import { createScopedStorage } from "@/lib/storage";
import { uiStorageKeys } from "@/lib/uiStorageKeys";
import { useDocumentsChangesStream } from "@/pages/Workspace/sections/Documents/shared/hooks/useDocumentsChangesStream";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";

const STREAM_CURSOR_LIMIT = 1;
const STREAM_CURSOR_SORT = '[{"id":"updatedAt","desc":true}]';
const MAX_DELTA_PAGES = 25;
const DELTA_LIMIT = 200;

type ConnectionState = "idle" | "connecting" | "open" | "closed";

type WorkspaceDocumentsStreamContextValue = {
  subscribe: (handler: (change: DocumentChangeEntry) => void) => () => void;
  connectionState: ConnectionState;
};

const WorkspaceDocumentsStreamContext = createContext<WorkspaceDocumentsStreamContextValue | null>(null);

export function WorkspaceDocumentsStreamProvider({ children }: { readonly children: ReactNode }) {
  const { workspace } = useWorkspaceContext();
  const queryClient = useQueryClient();
  const listenersRef = useRef(new Set<(change: DocumentChangeEntry) => void>());
  const [cursor, setCursor] = useState<string | null>(null);
  const resyncCursorRef = useRef<string | null>(null);

  const cursorStorage = useMemo(
    () => (workspace.id ? createScopedStorage(uiStorageKeys.documentsCursor(workspace.id)) : null),
    [workspace.id],
  );

  useEffect(() => {
    if (!cursorStorage) {
      setCursor(null);
      return;
    }
    const stored = cursorStorage.get<string>();
    setCursor(stored ?? null);
  }, [cursorStorage]);

  useEffect(() => {
    if (!cursorStorage || !cursor) return;
    cursorStorage.set(cursor);
  }, [cursor, cursorStorage]);

  useEffect(() => {
    if (cursor !== null || !resyncCursorRef.current) return;
    const next = resyncCursorRef.current;
    resyncCursorRef.current = null;
    setCursor(next);
  }, [cursor]);

  const cursorSeedQuery = useQuery({
    queryKey: ["documents-changes-cursor", workspace.id],
    queryFn: ({ signal }) =>
      fetchWorkspaceDocuments(
        workspace.id,
        {
          sort: STREAM_CURSOR_SORT,
          limit: STREAM_CURSOR_LIMIT,
        },
        signal,
      ),
    enabled: Boolean(workspace.id) && !cursor,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (cursor || !cursorSeedQuery.data?.meta.changesCursor) return;
    setCursor(cursorSeedQuery.data.meta.changesCursor);
  }, [cursor, cursorSeedQuery.data?.meta.changesCursor]);

  const subscribe = useCallback((handler: (change: DocumentChangeEntry) => void) => {
    listenersRef.current.add(handler);
    return () => {
      listenersRef.current.delete(handler);
    };
  }, []);

  const dispatchChange = useCallback((change: DocumentChangeEntry) => {
    listenersRef.current.forEach((handler) => {
      handler(change);
    });
  }, []);

  const applyIncomingChanges = useCallback(
    (entries: DocumentChangeEntry[], nextCursor?: string | null) => {
      let appliedCursor = cursor;
      entries.forEach((entry) => {
        dispatchChange(entry);
        if (entry.cursor) {
          appliedCursor = entry.cursor;
        }
      });
      if (entries.length === 0 && nextCursor) {
        appliedCursor = nextCursor;
      }
      if (appliedCursor && appliedCursor !== cursor) {
        setCursor(appliedCursor);
      }
    },
    [cursor, dispatchChange],
  );

  const invalidateWorkspaceDocuments = useCallback(() => {
    if (!workspace.id) return;
    queryClient.invalidateQueries({ queryKey: ["documents", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["sidebar", "assigned-documents", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["documents-preview-row", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["documents-preview-details", workspace.id] });
  }, [queryClient, workspace.id]);

  const catchUp = useCallback(async () => {
    if (!cursor || !workspace.id) return;
    let nextCursor = cursor;
    try {
      for (let pageIndex = 0; pageIndex < MAX_DELTA_PAGES; pageIndex += 1) {
        const changes = await fetchWorkspaceDocumentChanges(workspace.id, {
          cursor: nextCursor,
          limit: DELTA_LIMIT,
          includeRows: true,
        });
        const items = changes.items ?? [];
        applyIncomingChanges(items, changes.nextCursor ?? null);
        nextCursor = changes.nextCursor ?? nextCursor;
        if (items.length === 0) {
          break;
        }
        if (pageIndex === MAX_DELTA_PAGES - 1) {
          invalidateWorkspaceDocuments();
        }
      }
    } catch (error) {
      if (error instanceof DocumentChangesResyncError) {
        resyncCursorRef.current = error.latestCursor ?? null;
        setCursor(null);
        invalidateWorkspaceDocuments();
      }
    }
  }, [applyIncomingChanges, cursor, invalidateWorkspaceDocuments, workspace.id]);

  useEffect(() => {
    if (!workspace.id) return;
    const handleFocus = () => void catchUp();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void catchUp();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [catchUp, workspace.id]);

  const { connectionState } = useDocumentsChangesStream({
    workspaceId: workspace.id,
    cursor,
    enabled: Boolean(workspace.id && cursor),
    includeRows: true,
    onEvent: (change) => applyIncomingChanges([change]),
    onReady: (nextCursor) => {
      if (nextCursor) {
        setCursor(nextCursor);
      }
    },
    onResyncRequired: (latestCursor) => {
      resyncCursorRef.current = latestCursor ?? null;
      setCursor(null);
      invalidateWorkspaceDocuments();
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

export function useWorkspaceDocumentsChanges(handler: (change: DocumentChangeEntry) => void) {
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
