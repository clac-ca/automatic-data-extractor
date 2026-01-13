import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DocumentChangesResyncError,
  fetchWorkspaceDocumentChanges,
  fetchWorkspaceDocuments,
  fetchWorkspaceDocumentRowById,
  type DocumentChangeEntry,
  type DocumentListRow,
} from "@api/documents";
import { ApiError } from "@api/errors";
import type { FilterItem, FilterJoinOperator } from "@api/listing";
import { createScopedStorage } from "@lib/storage";
import { uiStorageKeys } from "@lib/uiStorageKeys";

import type { DocumentRow } from "../types";
import { useDocumentsChangesStream } from "./useDocumentsChangesStream";

type HydratedChange = DocumentChangeEntry & { row?: DocumentListRow | null };

type DocumentsState = {
  documentsById: Record<string, DocumentRow>;
  viewIds: string[];
  pageCount: number;
  total: number | null;
  isLoading: boolean;
  isFetching: boolean;
  error: string | null;
  cursor: string | null;
  changesCursor: string | null;
};

const DEFAULT_STATE: DocumentsState = {
  documentsById: {},
  viewIds: [],
  pageCount: 1,
  total: null,
  isLoading: false,
  isFetching: false,
  error: null,
  cursor: null,
  changesCursor: null,
};

const MAX_DELTA_PAGES = 25;
const DELTA_LIMIT = 200;

function mergeRow(existing: DocumentRow | undefined, next: DocumentListRow): DocumentRow {
  return {
    ...existing,
    ...next,
    uploadProgress: existing?.uploadProgress ?? null,
  };
}

function removeId(ids: string[], rowId: string) {
  const index = ids.indexOf(rowId);
  if (index === -1) return ids;
  const next = ids.slice();
  next.splice(index, 1);
  return next;
}

export function useDocumentsView({
  workspaceId,
  page,
  perPage,
  sort,
  filters,
  joinOperator,
  enabled = true,
}: {
  workspaceId: string;
  page: number;
  perPage: number;
  sort: string | null;
  filters: FilterItem[] | null;
  joinOperator: FilterJoinOperator | null;
  enabled?: boolean;
}) {
  const [state, setState] = useState<DocumentsState>(DEFAULT_STATE);
  const inFlightPagesRef = useRef(new Set<string>());
  const activeRequestRef = useRef<AbortController | null>(null);
  const viewKey = useMemo(() => {
    const filtersKey = filters?.length ? JSON.stringify(filters) : "";
    return [workspaceId, page, perPage, sort ?? "", filtersKey, joinOperator ?? ""].join("|");
  }, [workspaceId, page, perPage, sort, filters, joinOperator]);
  const viewKeyRef = useRef(viewKey);

  useEffect(() => {
    viewKeyRef.current = viewKey;
  }, [viewKey]);

  const cursorStorage = useMemo(
    () => (workspaceId ? createScopedStorage(uiStorageKeys.documentsCursor(workspaceId)) : null),
    [workspaceId],
  );

  useEffect(() => {
    if (!cursorStorage) return;
    const stored = cursorStorage.get<string>();
    setState((prev) => ({ ...prev, cursor: stored ?? prev.cursor }));
  }, [cursorStorage]);

  useEffect(() => {
    if (!cursorStorage || !state.cursor) return;
    cursorStorage.set(state.cursor);
  }, [cursorStorage, state.cursor]);

  const loadPage = useCallback(
    async (targetPage: number) => {
      if (!workspaceId || !enabled) return;
      const requestKey = `${viewKey}:${targetPage}`;
      if (inFlightPagesRef.current.has(requestKey)) return;
      inFlightPagesRef.current.add(requestKey);
      if (activeRequestRef.current) {
        activeRequestRef.current.abort();
      }
      const controller = new AbortController();
      activeRequestRef.current = controller;
      setState((prev) => ({
        ...prev,
        isLoading: prev.viewIds.length === 0,
        isFetching: true,
        error: null,
      }));
      try {
        const result = await fetchWorkspaceDocuments(workspaceId, {
          page: targetPage,
          perPage,
          sort,
          filters: filters?.length ? filters : null,
          joinOperator: joinOperator ?? undefined,
        }, controller.signal);
        if (activeRequestRef.current !== controller) return;
        if (viewKeyRef.current !== viewKey) return;
        const items = result.items ?? [];
        setState((prev) => {
          const nextById: Record<string, DocumentRow> = {};
          const nextIds: string[] = [];

          for (const row of items) {
            const mergedRow = mergeRow(prev.documentsById[row.id], row);
            nextById[row.id] = mergedRow;
            nextIds.push(row.id);
          }

          const nextCursor = prev.cursor ?? result.changesCursor ?? null;
          return {
            ...prev,
            documentsById: nextById,
            viewIds: nextIds,
            pageCount: result.pageCount ?? 1,
            total: typeof result.total === "number" ? result.total : prev.total,
            isLoading: false,
            isFetching: false,
            error: null,
            changesCursor: result.changesCursor ?? prev.changesCursor,
            cursor: nextCursor,
          };
        });
      } catch (error) {
        if (activeRequestRef.current !== controller) return;
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (viewKeyRef.current !== viewKey) return;
        setState((prev) => ({
          ...prev,
          isLoading: false,
          isFetching: false,
          error: error instanceof Error ? error.message : "Unable to load documents.",
        }));
      } finally {
        inFlightPagesRef.current.delete(requestKey);
        if (activeRequestRef.current === controller) {
          activeRequestRef.current = null;
        }
      }
    },
    [enabled, filters, joinOperator, perPage, sort, viewKey, workspaceId],
  );

  const refreshSnapshot = useCallback(() => {
    void loadPage(page);
  }, [loadPage, page]);

  useEffect(() => {
    if (!workspaceId || !enabled) return;
    void loadPage(page);
  }, [enabled, loadPage, page, workspaceId, viewKey]);

  const applyUpsert = useCallback(
    (prev: DocumentsState, entry: HydratedChange) => {
      const row = entry.row;
      if (!row) return prev;
      const existing = prev.documentsById[row.id];
      if (!existing) {
        if (page !== 1) {
          return prev;
        }
        const nextById = { ...prev.documentsById, [row.id]: mergeRow(undefined, row) };
        const nextIds = [row.id, ...prev.viewIds.filter((id) => id !== row.id)].slice(0, perPage);
        return { ...prev, documentsById: nextById, viewIds: nextIds };
      }

      const nextById = { ...prev.documentsById, [row.id]: mergeRow(existing, row) };
      return { ...prev, documentsById: nextById };
    },
    [page, perPage],
  );

  const applyDelete = useCallback((prev: DocumentsState, entry: HydratedChange) => {
    const documentId = entry.documentId;
    if (!documentId || !prev.documentsById[documentId]) {
      return prev;
    }
    const nextById = { ...prev.documentsById };
    delete nextById[documentId];
    return {
      ...prev,
      documentsById: nextById,
      viewIds: removeId(prev.viewIds, documentId),
    };
  }, []);

  const applyIncomingChanges = useCallback(
    (
      entries: HydratedChange[],
      { nextCursor = null }: { nextCursor?: string | null } = {},
    ) => {
      setState((prev) => {
        let next = prev;
        let appliedCursor = prev.cursor;

        for (const entry of entries) {
          if (entry.type === "document.changed") {
            next = applyUpsert(next, entry);
          } else if (entry.type === "document.deleted") {
            next = applyDelete(next, entry);
          }
          appliedCursor = entry.cursor ?? appliedCursor;
        }

        if (entries.length === 0 && nextCursor) {
          appliedCursor = nextCursor;
        }

        return {
          ...next,
          cursor: appliedCursor ?? next.cursor,
        };
      });
    },
    [applyDelete, applyUpsert],
  );

  const hydrateChange = useCallback(
    async (entry: DocumentChangeEntry): Promise<HydratedChange> => {
      if (entry.type === "document.deleted") {
        return entry;
      }
      if (!entry.documentId) {
        return entry;
      }
      if (entry.row) {
        return entry as HydratedChange;
      }
      try {
        const row = await fetchWorkspaceDocumentRowById(workspaceId, entry.documentId);
        return { ...entry, row };
      } catch (error) {
        if (error instanceof ApiError) {
          return entry;
        }
      }
      return entry;
    },
    [workspaceId],
  );

  const catchUp = useCallback(async () => {
    if (!state.cursor || !workspaceId || !enabled) return;
    let cursor = state.cursor;
    try {
      for (let pageIndex = 0; pageIndex < MAX_DELTA_PAGES; pageIndex += 1) {
        // eslint-disable-next-line no-await-in-loop
        const changes = await fetchWorkspaceDocumentChanges(
          workspaceId,
          { cursor, limit: DELTA_LIMIT },
        );
        const items = changes.items ?? [];
        // eslint-disable-next-line no-await-in-loop
        const hydrated = await Promise.all(items.map(hydrateChange));
        applyIncomingChanges(hydrated, { nextCursor: changes.nextCursor ?? null });
        cursor = changes.nextCursor ?? cursor;
        if (items.length === 0) {
          break;
        }
        if (pageIndex === MAX_DELTA_PAGES - 1) {
          void refreshSnapshot();
        }
      }
    } catch (error) {
      if (error instanceof DocumentChangesResyncError) {
        setState((prev) => ({ ...prev, cursor: error.latestCursor }));
        void refreshSnapshot();
      }
    }
  }, [applyIncomingChanges, enabled, hydrateChange, refreshSnapshot, state.cursor, workspaceId]);

  useEffect(() => {
    if (!enabled || !workspaceId) return;
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
  }, [catchUp, enabled, workspaceId]);

  useDocumentsChangesStream({
    workspaceId,
    cursor: state.cursor,
    enabled: enabled && Boolean(state.cursor),
    includeRows: true,
    onEvent: (change) => {
      void applyIncomingChanges([change]);
    },
    onReady: (nextCursor) => {
      if (!nextCursor) return;
      setState((prev) => (prev.cursor === nextCursor ? prev : { ...prev, cursor: nextCursor }));
    },
    onResyncRequired: (latestCursor, _oldestCursor) => {
      if (latestCursor) {
        setState((prev) => ({ ...prev, cursor: latestCursor }));
      }
      void refreshSnapshot();
    },
  });

  const updateRow = useCallback(
    (documentId: string, updates: Partial<DocumentRow>) => {
      setState((prev) => {
        const existing = prev.documentsById[documentId];
        if (!existing) return prev;
        const nextById = { ...prev.documentsById, [documentId]: { ...existing, ...updates } };
        return { ...prev, documentsById: nextById };
      });
    },
    [],
  );

  const upsertRow = useCallback(
    (row: DocumentListRow) => {
      setState((prev) =>
        applyUpsert(
          prev,
          {
            type: "document.changed",
            documentId: row.id,
            documentVersion: row.version,
            row,
            cursor: "0",
            occurredAt: new Date().toISOString(),
          } as HydratedChange,
        ),
      );
    },
    [applyUpsert],
  );

  const removeRow = useCallback(
    (documentId: string) => {
      setState((prev) =>
        applyDelete(
          prev,
          {
            type: "document.deleted",
            documentId,
            documentVersion: 0,
            cursor: "0",
            occurredAt: new Date().toISOString(),
          } as HydratedChange,
        ),
      );
    },
    [applyDelete],
  );

  const setUploadProgress = useCallback(
    (documentId: string, percent: number | null) => {
      updateRow(documentId, { uploadProgress: percent });
    },
    [updateRow],
  );

  const rows = useMemo(
    () => state.viewIds.map((id) => state.documentsById[id]).filter(Boolean),
    [state.documentsById, state.viewIds],
  );

  return {
    rows,
    documentsById: state.documentsById,
    pageCount: state.pageCount,
    total: state.total,
    isLoading: state.isLoading,
    isFetching: state.isFetching,
    error: state.error,
    refreshSnapshot,
    updateRow,
    upsertRow,
    removeRow,
    setUploadProgress,
    cursor: state.cursor,
  };
}
