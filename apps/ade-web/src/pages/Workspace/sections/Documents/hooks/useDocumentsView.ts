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
import { useDebouncedCallback } from "@hooks/use-debounced-callback";
import { createScopedStorage } from "@lib/storage";
import { uiStorageKeys } from "@lib/uiStorageKeys";

import {
  buildDocumentsComparator,
  evaluateDocumentFilters,
  parseSortTokens,
  supportsSortTokens,
} from "../data-table/utils";
import type { DocumentRow } from "../types";
import { useDocumentsChangesStream } from "./useDocumentsChangesStream";

type HydratedChange = DocumentChangeEntry & { row?: DocumentListRow | null };

type DocumentsState = {
  documentsById: Record<string, DocumentRow>;
  viewIds: string[];
  pageCount: number;
  total: number | null;
  lastPage: number;
  isLoading: boolean;
  isFetchingNextPage: boolean;
  error: string | null;
  cursor: string | null;
  changesCursor: string | null;
  queuedChanges: HydratedChange[];
};

const DEFAULT_STATE: DocumentsState = {
  documentsById: {},
  viewIds: [],
  pageCount: 1,
  total: null,
  lastPage: 0,
  isLoading: false,
  isFetchingNextPage: false,
  error: null,
  cursor: null,
  changesCursor: null,
  queuedChanges: [],
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

function findInsertIndex(
  ids: string[],
  row: DocumentListRow,
  byId: Record<string, DocumentRow>,
  comparator: (left: DocumentListRow, right: DocumentListRow) => number,
) {
  let low = 0;
  let high = ids.length;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    const midRow = byId[ids[mid]];
    if (!midRow) {
      high = mid;
      continue;
    }
    const diff = comparator(row, midRow);
    if (diff < 0) {
      high = mid;
    } else {
      low = mid + 1;
    }
  }
  return low;
}

function insertSorted(
  ids: string[],
  row: DocumentListRow,
  byId: Record<string, DocumentRow>,
  comparator: (left: DocumentListRow, right: DocumentListRow) => number,
) {
  const index = findInsertIndex(ids, row, byId, comparator);
  const next = ids.slice();
  next.splice(index, 0, row.id);
  return next;
}

function removeId(ids: string[], rowId: string) {
  const index = ids.indexOf(rowId);
  if (index === -1) return ids;
  const next = ids.slice();
  next.splice(index, 1);
  return next;
}

function addQueuedChange(changes: HydratedChange[], entry: HydratedChange) {
  if (changes.some((item) => item.cursor === entry.cursor)) {
    return changes;
  }
  const next = changes.slice();
  next.push(entry);
  return next;
}

export function useDocumentsView({
  workspaceId,
  perPage,
  sort,
  filters,
  joinOperator,
  q,
  enabled = true,
  isAtTop = true,
  visibleStartIndex = null,
}: {
  workspaceId: string;
  perPage: number;
  sort: string | null;
  filters: FilterItem[];
  joinOperator: FilterJoinOperator | null;
  q: string | null;
  enabled?: boolean;
  isAtTop?: boolean;
  visibleStartIndex?: number | null;
}) {
  const [state, setState] = useState<DocumentsState>(DEFAULT_STATE);
  const inFlightPagesRef = useRef(new Set<string>());
  const pendingRequestIdsRef = useRef(new Set<string>());
  const isAtTopRef = useRef(isAtTop);
  const visibleStartIndexRef = useRef<number | null>(visibleStartIndex ?? null);
  const viewKey = useMemo(
    () =>
      [
        workspaceId,
        perPage,
        sort ?? "",
        filters.length ? JSON.stringify(filters) : "",
        joinOperator ?? "",
        q ?? "",
      ].join("|"),
    [workspaceId, perPage, sort, filters, joinOperator, q],
  );
  const viewKeyRef = useRef(viewKey);

  useEffect(() => {
    viewKeyRef.current = viewKey;
  }, [viewKey]);

  useEffect(() => {
    isAtTopRef.current = isAtTop;
  }, [isAtTop]);

  useEffect(() => {
    visibleStartIndexRef.current =
      typeof visibleStartIndex === "number" ? visibleStartIndex : null;
  }, [visibleStartIndex]);

  const sortTokens = useMemo(() => parseSortTokens(sort), [sort]);
  const comparator = useMemo(() => buildDocumentsComparator(sortTokens), [sortTokens]);
  const sortSupported = useMemo(() => supportsSortTokens(sortTokens), [sortTokens]);

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

  const resetView = useCallback(() => {
    setState((prev) => ({
      ...DEFAULT_STATE,
      cursor: prev.cursor,
      changesCursor: prev.changesCursor,
    }));
  }, []);

  const applyUpsert = useCallback(
    (prev: DocumentsState, entry: HydratedChange) => {
      const row = entry.row;
      if (!row) return { state: prev, requiresRefresh: false };

      const existing = prev.documentsById[row.id];
      const incomingVersion = entry.documentVersion ?? row.version;
      if (existing?.version && incomingVersion && incomingVersion < existing.version) {
        return { state: prev, requiresRefresh: false };
      }

      const nextById = { ...prev.documentsById };
      const mergedRow = mergeRow(existing, row);
      nextById[row.id] = mergedRow;

      if (!sortSupported) {
        return {
          state: {
            ...prev,
            documentsById: nextById,
          },
          requiresRefresh: true,
        };
      }

      const { matches, requiresRefresh } = evaluateDocumentFilters(
        nextById[row.id],
        filters,
        joinOperator,
        q,
      );
      if (requiresRefresh) {
        return {
          state: {
            ...prev,
            documentsById: nextById,
          },
          requiresRefresh: true,
        };
      }

      let nextIds = prev.viewIds;
      if (!matches) {
        nextIds = removeId(nextIds, row.id);
      } else {
        nextIds = removeId(nextIds, row.id);
        nextIds = insertSorted(nextIds, mergedRow, nextById, comparator);
      }

      return { state: { ...prev, documentsById: nextById, viewIds: nextIds }, requiresRefresh: false };
    },
    [comparator, filters, joinOperator, q, sortSupported],
  );

  const applyDelete = useCallback((prev: DocumentsState, entry: HydratedChange) => {
    const documentId = entry.documentId;
    if (!documentId) {
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

  const markNeedsRefresh = useDebouncedCallback(() => {
    void refreshSnapshot();
  }, 600);

  const applyChanges = useCallback(
    (
      entries: HydratedChange[],
      {
        allowQueue = true,
        nextCursor = null,
      }: { allowQueue?: boolean; nextCursor?: string | null } = {},
    ) => {
      setState((prev) => {
        let next = prev;
        let queued = prev.queuedChanges;
        let appliedCursor = prev.cursor;
        let queuedAdded = false;

        for (const entry of entries) {
          const requestId = entry.clientRequestId ?? null;
          const isLocal = requestId ? pendingRequestIdsRef.current.has(requestId) : false;
          if (requestId && isLocal) {
            pendingRequestIdsRef.current.delete(requestId);
          }

          let shouldQueue = false;
          if (
            allowQueue &&
            !isLocal &&
            !isAtTopRef.current &&
            entry.type === "document.changed" &&
            entry.row
          ) {
            const startIndex = visibleStartIndexRef.current;
            if (startIndex == null) {
              shouldQueue = true;
            } else if (sortSupported) {
              const existing = next.documentsById[entry.row.id];
              const mergedRow = mergeRow(existing, entry.row);
              const { matches, requiresRefresh } = evaluateDocumentFilters(
                mergedRow,
                filters,
                joinOperator,
                q,
              );
              if (!requiresRefresh && matches) {
                const currentIndex = next.viewIds.indexOf(entry.row.id);
                if (currentIndex === -1 || currentIndex >= startIndex) {
                  const candidateIds =
                    currentIndex === -1 ? next.viewIds : removeId(next.viewIds, entry.row.id);
                  const insertIndex = findInsertIndex(
                    candidateIds,
                    mergedRow,
                    next.documentsById,
                    comparator,
                  );
                  shouldQueue = insertIndex < startIndex;
                }
              }
            }
          }
          if (shouldQueue) {
            queued = addQueuedChange(queued, entry);
            queuedAdded = true;
            continue;
          }

          if (entry.type === "document.changed") {
            const result = applyUpsert(next, entry);
            if (result.requiresRefresh) {
              markNeedsRefresh();
            }
            next = result.state;
          } else if (entry.type === "document.deleted") {
            next = applyDelete(next, entry);
          }

          appliedCursor = entry.cursor;
        }

        if (!queuedAdded && entries.length === 0 && nextCursor) {
          appliedCursor = nextCursor;
        }

        return {
          ...next,
          cursor: appliedCursor ?? next.cursor,
          queuedChanges: queued,
        };
      });
    },
    [applyDelete, applyUpsert, comparator, filters, joinOperator, markNeedsRefresh, q, sortSupported],
  );

  const hydrateChange = useCallback(
    async (entry: DocumentChangeEntry): Promise<HydratedChange> => {
      if (entry.type === "document.deleted") {
        return entry;
      }
      try {
        const row = await fetchWorkspaceDocumentRowById(workspaceId, entry.documentId);
        return { ...entry, row };
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return { ...entry, type: "document.deleted" };
        }
        markNeedsRefresh();
        return entry;
      }
    },
    [markNeedsRefresh, workspaceId],
  );

  const applyIncomingChanges = useCallback(
    async (
      entries: DocumentChangeEntry[],
      {
        allowQueue = true,
        nextCursor = null,
      }: { allowQueue?: boolean; nextCursor?: string | null } = {},
    ) => {
      if (!entries.length) {
        applyChanges([], { allowQueue, nextCursor });
        return;
      }
      const hydrated = await Promise.all(entries.map((entry) => hydrateChange(entry)));
      applyChanges(hydrated, { allowQueue, nextCursor });
    },
    [applyChanges, hydrateChange],
  );

  const applyQueuedChanges = useCallback(() => {
    setState((prev) => {
      if (!prev.queuedChanges.length) return prev;
      const ordered = prev.queuedChanges.slice();
      const nextState = {
        ...prev,
        queuedChanges: [],
      };
      let updated = nextState;
      for (const entry of ordered) {
        if (entry.type === "document.changed") {
          const result = applyUpsert(updated, entry);
          if (result.requiresRefresh) {
            markNeedsRefresh();
          }
          updated = result.state;
        } else if (entry.type === "document.deleted") {
          updated = applyDelete(updated, entry);
        }
        updated = { ...updated, cursor: entry.cursor };
      }
      return updated;
    });
  }, [applyDelete, applyUpsert, markNeedsRefresh]);

  useEffect(() => {
    if (!isAtTop || state.queuedChanges.length === 0) return;
    applyQueuedChanges();
  }, [applyQueuedChanges, isAtTop, state.queuedChanges.length]);

  const loadPage = useCallback(
    async (page: number) => {
      if (!workspaceId || !enabled) return;
      const requestKey = `${viewKey}:${page}`;
      if (inFlightPagesRef.current.has(requestKey)) return;
      inFlightPagesRef.current.add(requestKey);
      const isInitial = page === 1;
      setState((prev) => ({
        ...prev,
        isLoading: isInitial,
        isFetchingNextPage: !isInitial,
        error: null,
      }));
      try {
        const result = await fetchWorkspaceDocuments(workspaceId, {
          page,
          perPage,
          sort,
          filters,
          joinOperator: joinOperator ?? undefined,
          q,
        });
        if (viewKeyRef.current !== viewKey) return;
        const items = result.items ?? [];
        setState((prev) => {
          const nextById = { ...prev.documentsById };
          let nextIds = isInitial ? [] : prev.viewIds;

          for (const row of items) {
            const mergedRow = mergeRow(nextById[row.id], row);
            nextById[row.id] = mergedRow;
            if (sortSupported) {
              nextIds = removeId(nextIds, row.id);
              nextIds = insertSorted(nextIds, mergedRow, nextById, comparator);
            }
          }

          const nextCursor = prev.cursor ?? result.changesCursor ?? null;
          return {
            ...prev,
            documentsById: nextById,
            viewIds: sortSupported ? nextIds : items.map((item) => item.id),
            pageCount: result.pageCount ?? 1,
            total: typeof result.total === "number" ? result.total : prev.total,
            lastPage: page,
            isLoading: false,
            isFetchingNextPage: false,
            error: null,
            changesCursor: result.changesCursor ?? prev.changesCursor,
            cursor: nextCursor,
          };
        });
      } catch (error) {
        if (viewKeyRef.current !== viewKey) return;
        setState((prev) => ({
          ...prev,
          isLoading: false,
          isFetchingNextPage: false,
          error: error instanceof Error ? error.message : "Unable to load documents.",
        }));
      } finally {
        inFlightPagesRef.current.delete(requestKey);
      }
    },
    [
      comparator,
      enabled,
      filters,
      joinOperator,
      perPage,
      q,
      sort,
      sortSupported,
      viewKey,
      workspaceId,
    ],
  );

  const refreshSnapshot = useCallback(async () => {
    if (!workspaceId || !enabled) return;
    const targetPage = Math.max(1, state.lastPage || 1);
    resetView();
    for (let page = 1; page <= targetPage; page += 1) {
      // eslint-disable-next-line no-await-in-loop
      await loadPage(page);
    }
  }, [enabled, loadPage, resetView, state.lastPage, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !enabled) return;
    resetView();
    void loadPage(1);
  }, [enabled, loadPage, resetView, viewKey, workspaceId]);

  const fetchNextPage = useCallback(() => {
    if (state.isFetchingNextPage || state.isLoading) return;
    if (state.lastPage >= state.pageCount) return;
    void loadPage(state.lastPage + 1);
  }, [loadPage, state.isFetchingNextPage, state.isLoading, state.lastPage, state.pageCount]);

  const catchUp = useCallback(async () => {
    if (!state.cursor || !workspaceId || !enabled) return;
    let cursor = state.cursor;
    let needsResync = false;
    try {
      for (let page = 0; page < MAX_DELTA_PAGES; page += 1) {
        // eslint-disable-next-line no-await-in-loop
        const changes = await fetchWorkspaceDocumentChanges(
          workspaceId,
          { cursor, limit: DELTA_LIMIT },
        );
        const items = changes.items ?? [];
        await applyIncomingChanges(items, {
          allowQueue: true,
          nextCursor: changes.nextCursor ?? null,
        });
        cursor = changes.nextCursor ?? cursor;
        if (items.length === 0) {
          break;
        }
        if (page === MAX_DELTA_PAGES - 1) {
          needsResync = true;
        }
      }
      if (needsResync) {
        void refreshSnapshot();
      }
    } catch (error) {
      if (error instanceof DocumentChangesResyncError) {
        setState((prev) => ({ ...prev, cursor: error.latestCursor }));
        void refreshSnapshot();
        return;
      }
    }
  }, [applyIncomingChanges, enabled, refreshSnapshot, state.cursor, workspaceId]);

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

  const { connectionState } = useDocumentsChangesStream({
    workspaceId,
    cursor: state.cursor,
    enabled: enabled && Boolean(state.cursor),
    onEvent: (change) => {
      void applyIncomingChanges([change], { allowQueue: true });
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
        ).state,
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

  const setUploadProgress = useCallback((documentId: string, percent: number | null) => {
    updateRow(documentId, { uploadProgress: percent });
  }, [updateRow]);

  const registerClientRequestId = useCallback((requestId: string) => {
    pendingRequestIdsRef.current.add(requestId);
  }, []);

  const clearClientRequestId = useCallback((requestId: string) => {
    pendingRequestIdsRef.current.delete(requestId);
  }, []);

  const rows = useMemo(
    () => state.viewIds.map((id) => state.documentsById[id]).filter(Boolean),
    [state.documentsById, state.viewIds],
  );

  return {
    rows,
    documentsById: state.documentsById,
    pageCount: state.pageCount,
    total: state.total,
    hasNextPage: state.lastPage < state.pageCount,
    isLoading: state.isLoading,
    isFetchingNextPage: state.isFetchingNextPage,
    error: state.error,
    fetchNextPage,
    refreshSnapshot,
    updateRow,
    upsertRow,
    removeRow,
    setUploadProgress,
    registerClientRequestId,
    clearClientRequestId,
    queuedChanges: state.queuedChanges,
    applyQueuedChanges,
    connectionState,
    cursor: state.cursor,
  };
}
