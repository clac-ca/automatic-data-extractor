import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MutableRefObject,
} from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";

import { ApiError } from "@api";
import { useConfigurationsQuery } from "@hooks/configurations";
import { useNotifications } from "@components/providers/notifications";
import {
  archiveWorkspaceDocument,
  archiveWorkspaceDocumentsBatch,
  deleteWorkspaceDocument,
  deleteWorkspaceDocumentsBatch,
  documentChangesStreamUrl,
  fetchWorkspaceDocuments,
  fetchWorkspaceDocumentRowById,
  patchDocumentTags,
  patchDocumentTagsBatch,
  patchWorkspaceDocument,
  restoreWorkspaceDocument,
  restoreWorkspaceDocumentsBatch,
  streamDocumentChanges,
  type DocumentUploadResponse,
} from "@api/documents";
import { buildWeakEtag } from "@api/etag";
import { createRunForDocument, fetchRunMetrics, fetchWorkspaceRunsForDocument } from "@api/runs/api";
import { listWorkspaceMembers } from "@api/workspaces/api";
import {
  useUploadManager,
  type UploadManagerItem,
  type UploadManagerQueueItem,
  type UploadManagerSummary,
} from "@hooks/documents/uploadManager";
import { documentsKeys } from "@hooks/documents/keys";

import type { RunResource } from "@schema";

import { DEFAULT_LIST_SETTINGS, normalizeListSettings, resolveRefreshIntervalMs } from "../listSettings";
import { mergeDocumentChangeIntoPages } from "../changeFeed";
import type {
  BoardColumn,
  BoardGroup,
  DocumentComment,
  DocumentEntry,
  DocumentListRow,
  DocumentPageResult,
  DocumentChangeEntry,
  DocumentsFilters,
  DocumentStatus,
  ListSettings,
  RunMetricsResource,
  SavedView,
  ViewMode,
  WorkbookPreview,
  WorkspacePerson,
} from "../types";
import {
  copyToClipboard,
  downloadOriginalDocument,
  downloadRunOutput,
  downloadRunOutputById,
  fetchWorkbookPreview,
  fileTypeFromName,
  getDocumentOutputRun,
  parseTimestamp,
  runHasDownloadableOutput,
  runOutputDownloadUrl,
  shortId,
} from "../utils";
import {
  ACTIVE_DOCUMENT_STATUSES,
  type BuiltInViewId,
  DEFAULT_DOCUMENT_FILTERS,
  UNASSIGNED_KEY,
  buildDocumentFilterItems,
  buildFiltersForBuiltInView,
  resolveActiveViewId,
} from "../filters";

type WorkbenchState = {
  viewMode: ViewMode;
  groupBy: BoardGroup;
  search: string;
  selectedIds: Set<string>;
  activeId: string | null;
  previewOpen: boolean;
  activeSheetId: string | null;

  filters: DocumentsFilters;
  activeViewId: string;
  saveViewOpen: boolean;
  selectedRunId: string | null;

  listSettings: ListSettings;
};

type WorkbenchDerived = {
  now: number;
  documents: DocumentEntry[];
  visibleDocuments: DocumentEntry[];
  activeDocument: DocumentEntry | null;

  boardColumns: BoardColumn[];

  isLoading: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;

  // People
  people: WorkspacePerson[];
  currentUserKey: string;

  // Runs
  runs: RunResource[];
  runsLoading: boolean;
  selectedRunId: string | null;
  activeRun: RunResource | null;
  runLoading: boolean;
  runMetrics: RunMetricsResource | null;
  runMetricsLoading: boolean;
  runMetricsError: boolean;

  // Output preview
  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;

  // Empty states
  showNoDocuments: boolean;
  showNoResults: boolean;
  allVisibleSelected: boolean;
  someVisibleSelected: boolean;

  // Saved views
  savedViews: SavedView[];

  // Notes
  activeComments: DocumentComment[];

  // Counts for sidebar
  counts: {
    total: number;
    active: number;
    assignedToMe: number;
    assignedToMeOrUnassigned: number;
    unassigned: number;
    processed: number;
    processing: number;
    failed: number;
    archived: number;
  };

  lastUpdatedAt: number | null;
  isRefreshing: boolean;

  changesCursor: string | null;
  configMissing: boolean;
  processingPaused: boolean;

  uploads: {
    items: UploadManagerItem<DocumentUploadResponse>[];
    summary: UploadManagerSummary;
  };
};

type WorkbenchRefs = {
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
};

type WorkbenchActions = {
  setSearch: (value: string) => void;
  setViewMode: (value: ViewMode) => void;
  setGroupBy: (value: BoardGroup) => void;

  updateSelection: (id: string, options?: { mode?: "toggle" | "range"; checked?: boolean }) => void;
  selectAllVisible: () => void;
  clearSelection: () => void;

  openPreview: (id: string) => void;
  closePreview: () => void;

  setActiveSheetId: (id: string) => void;

  queueUploads: (items: UploadManagerQueueItem[]) => void;
  handleUploadClick: () => void;
  pauseUpload: (uploadId: string) => void;
  resumeUpload: (uploadId: string) => void;
  retryUpload: (uploadId: string) => void;
  cancelUpload: (uploadId: string) => void;
  removeUpload: (uploadId: string) => void;
  clearCompletedUploads: () => void;

  refreshDocuments: () => void;
  loadMore: () => void;

  handleKeyNavigate: (event: ReactKeyboardEvent<HTMLDivElement>) => void;

  // Filters & views
  setFilters: (next: DocumentsFilters) => void;
  setListSettings: (next: ListSettings) => void;
  setBuiltInView: (id: BuiltInViewId) => void;
  selectSavedView: (viewId: string) => void;
  openSaveView: () => void;
  closeSaveView: () => void;
  saveView: (name: string) => void;
  deleteView: (viewId: string) => void;

  // Tags (persisted)
  updateTagsOptimistic: (documentId: string, nextTags: string[]) => void;

  // Assignment
  assignDocument: (documentId: string, assigneeKey: string | null) => void;
  pickUpDocument: (documentId: string) => void;

  // Notes (local-first)
  addComment: (documentId: string, body: string, mentions: { key: string; label: string }[]) => void;
  editComment: (documentId: string, commentId: string, body: string, mentions: { key: string; label: string }[]) => void;
  deleteComment: (documentId: string, commentId: string) => void;

  // Runs
  selectRun: (runId: string) => void;

  // Downloads & link
  downloadOutput: (doc: DocumentEntry | null) => void;
  downloadOutputFromRow: (doc: DocumentEntry) => void;
  downloadOriginal: (doc: DocumentEntry | null) => void;
  reprocess: (doc: DocumentEntry | null) => void;
  copyLink: (doc: DocumentEntry | null) => void;
  deleteDocument: (documentId: string) => void;
  archiveDocument: (documentId: string) => void;
  restoreDocument: (documentId: string) => void;

  // Bulk actions
  bulkDeleteDocuments: (documentIds?: string[]) => void;
  bulkArchiveDocuments: (documentIds?: string[]) => void;
  bulkRestoreDocuments: (documentIds?: string[]) => void;
  bulkUpdateTags: (payload: { add: string[]; remove: string[] }) => void;
  bulkDownloadOriginals: () => void;
  bulkDownloadOutputs: () => void;
};

export type WorkbenchModel = {
  state: WorkbenchState;
  derived: WorkbenchDerived;
  refs: WorkbenchRefs;
  actions: WorkbenchActions;
};

const STATUS_ORDER: DocumentStatus[] = ["uploaded", "processing", "processed", "failed", "archived"];

const DOCUMENTS_STORAGE_KEYS = {
  views: (workspaceId: string) => `ade.documents.views.${workspaceId}`,
  viewsLegacy: (workspaceId: string) => `ade.documents.v10.views.${workspaceId}`,
  comments: (workspaceId: string) => `ade.documents.comments.${workspaceId}`,
  commentsLegacy: (workspaceId: string) => `ade.documents.v10.comments.${workspaceId}`,
  listSettings: (workspaceId: string) => `ade.documents.list_settings.${workspaceId}`,
};

function safeJsonParse<T>(value: string | null): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

function loadSavedViews(workspaceId: string): SavedView[] {
  if (typeof window === "undefined") return [];
  const raw =
    window.localStorage.getItem(DOCUMENTS_STORAGE_KEYS.views(workspaceId)) ??
    window.localStorage.getItem(DOCUMENTS_STORAGE_KEYS.viewsLegacy(workspaceId));
  const parsed = safeJsonParse<SavedView[]>(raw);
  if (!parsed) return [];
  return parsed.map((v) => ({
    ...v,
    filters: {
      ...DEFAULT_DOCUMENT_FILTERS,
      ...(v.filters ?? {}),
      tagMode: v.filters?.tagMode ?? "any",
      assignees: v.filters?.assignees ?? [],
    },
  }));
}

function storeSavedViews(workspaceId: string, views: SavedView[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(DOCUMENTS_STORAGE_KEYS.views(workspaceId), JSON.stringify(views));
}

function loadComments(workspaceId: string): Record<string, DocumentComment[]> {
  if (typeof window === "undefined") return {};
  const raw =
    window.localStorage.getItem(DOCUMENTS_STORAGE_KEYS.comments(workspaceId)) ??
    window.localStorage.getItem(DOCUMENTS_STORAGE_KEYS.commentsLegacy(workspaceId));
  const parsed = safeJsonParse<Record<string, DocumentComment[]>>(raw);
  return parsed ?? {};
}

function storeComments(workspaceId: string, map: Record<string, DocumentComment[]>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(DOCUMENTS_STORAGE_KEYS.comments(workspaceId), JSON.stringify(map));
}

function loadListSettings(workspaceId: string): ListSettings {
  if (typeof window === "undefined") return DEFAULT_LIST_SETTINGS;
  const raw = window.localStorage.getItem(DOCUMENTS_STORAGE_KEYS.listSettings(workspaceId));
  const parsed = safeJsonParse<Partial<ListSettings>>(raw);
  return normalizeListSettings(parsed);
}

function storeListSettings(workspaceId: string, settings: ListSettings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(DOCUMENTS_STORAGE_KEYS.listSettings(workspaceId), JSON.stringify(settings));
}

/**
 * High-performance architecture notes:
 * - Single real-time stream for documents: /documents/changes/stream
 * - NO per-document / per-run SSE streams (that explodes connection count on bulk uploads)
 * - List rows are wrapped with a small stable cache so unchanged rows keep reference identity.
 */
export function useDocumentsModel({
  workspaceId,
  currentUserLabel,
  currentUserId,
  currentUserEmail,
  processingPaused,
  initialFilters,
}: {
  workspaceId: string;
  currentUserLabel: string;
  currentUserId: string;
  currentUserEmail: string;
  processingPaused: boolean;
  initialFilters?: DocumentsFilters;
}): WorkbenchModel {
  const { notifyToast } = useNotifications();
  const queryClient = useQueryClient();

  const currentUserKey = `user:${currentUserId}`;
  const initialFiltersValue = initialFilters ?? DEFAULT_DOCUMENT_FILTERS;
  const initialSavedViews = useMemo(() => loadSavedViews(workspaceId), [workspaceId]);

  // UI state
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [groupBy, setGroupBy] = useState<BoardGroup>("status");
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const [filters, setFilters] = useState<DocumentsFilters>(initialFiltersValue);
  const [activeViewId, setActiveViewId] = useState<string>(() =>
    resolveActiveViewId(initialFiltersValue, "", initialSavedViews, currentUserKey),
  );
  const [saveViewOpen, setSaveViewOpen] = useState(false);
  const [listSettings, setListSettings] = useState<ListSettings>(() => loadListSettings(workspaceId));

  const [savedViews, setSavedViews] = useState<SavedView[]>(() => initialSavedViews);
  const [commentsByDocId, setCommentsByDocId] = useState<Record<string, DocumentComment[]>>(() =>
    loadComments(workspaceId),
  );

  const [changesCursor, setChangesCursor] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  // Refs
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const selectionAnchorRef = useRef<string | null>(null);
  const shiftPressedRef = useRef(false);

  const uploadCreatedAtRef = useRef(new Map<string, number>());
  const handledUploadsRef = useRef(new Set<string>());
  const uploadIdMapRef = useRef(new Map<string, string>());

  const changesCursorRef = useRef<string | null>(null);
  const changeStreamControllerRef = useRef<AbortController | null>(null);

  const pendingChangesRef = useRef<DocumentChangeEntry[]>([]);
  const flushTimerRef = useRef<number | null>(null);
  const lastChangeCursorRef = useRef<string | null>(null);

  const refreshTimerRef = useRef<number | null>(null);
  const refreshInFlightRef = useRef(false);
  const refreshQueuedRef = useRef(false);

  // Small cache so unchanged API rows keep stable identity in the grid.
  const apiEntryCacheRef = useRef(
    new Map<
      string,
      {
        row: DocumentListRow;
        assigneeKey: string | null;
        assigneeLabel: string | null;
        uploaderLabel: string | null;
        commentCount: number;
        entry: DocumentEntry;
      }
    >(),
  );

  // Tick clock
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  // Global key handling
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewOpen(false);
      if (event.key === "Shift") shiftPressedRef.current = true;
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === "Shift") shiftPressedRef.current = false;
    };
    const handleBlur = () => {
      shiftPressedRef.current = false;
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", handleBlur);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);
    };
  }, []);

  // Workspace change reload local state
  useEffect(() => {
    setSavedViews(loadSavedViews(workspaceId));
    setCommentsByDocId(loadComments(workspaceId));
    setListSettings(loadListSettings(workspaceId));
    uploadIdMapRef.current.clear();
  }, [workspaceId]);

  // Persist list settings
  useEffect(() => {
    if (!workspaceId) return;
    storeListSettings(workspaceId, listSettings);
  }, [listSettings, workspaceId]);

  // Uploads
  const uploadManager = useUploadManager({ workspaceId });

  // Configurations
  const configurationsQuery = useConfigurationsQuery({ workspaceId });
  const { refetch: refetchConfigurations } = configurationsQuery;

  const activeConfiguration = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    return items.find((config) => config.status === "active") ?? null;
  }, [configurationsQuery.data?.items]);

  const configMissing = configurationsQuery.isSuccess && !activeConfiguration;

  // Query key
  const sort = "-createdAt";
  const listKey = useMemo(
    () =>
      documentsKeys.list(workspaceId, {
        sort,
        pageSize: listSettings.pageSize,
        filters,
        search,
      }),
    [filters, listSettings.pageSize, search, sort, workspaceId],
  );

  // Refresh strategy
  const refreshInterval = useMemo(() => resolveRefreshIntervalMs(listSettings.refreshInterval), [listSettings.refreshInterval]);
  const changeDetectionEnabled = listSettings.refreshInterval === "auto";

  // If change detection (SSE) is enabled, don't also poll. Refresh is triggered via SSE updatesAvailable.
  const queryRefetchInterval = useMemo(() => {
    if (changeDetectionEnabled) return false;
    return refreshInterval;
  }, [changeDetectionEnabled, refreshInterval]);

  const searchValue = search.trim();
  const q = searchValue.length >= 2 ? searchValue : null;
  const filterItems = useMemo(() => buildDocumentFilterItems(filters), [filters]);

  // Documents query (server-projected list rows)
  const documentsQuery = useInfiniteQuery<DocumentPageResult>({
    queryKey: listKey,
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort,
          page: typeof pageParam === "number" ? pageParam : 1,
          perPage: listSettings.pageSize,
          filters: filterItems,
          q,
        },
        signal,
      ),
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pageCount ? lastPage.page + 1 : undefined,
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    refetchInterval: queryRefetchInterval,
  });

  const { refetch: refetchDocuments } = documentsQuery;

  const documentsRaw = useMemo(
    () => documentsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [documentsQuery.data?.pages],
  );

  const documentIdsSet = useMemo(() => new Set(documentsRaw.map((d) => d.id)), [documentsRaw]);

  // Establish baseline cursor from list responses
  useEffect(() => {
    const firstPage = documentsQuery.data?.pages[0];
    const cursor = firstPage?.changesCursor ?? firstPage?.changesCursorHeader ?? null;
    if (!cursor) return;
    if (changesCursorRef.current === cursor) return;
    changesCursorRef.current = cursor;
    lastChangeCursorRef.current = cursor;
    setChangesCursor(cursor);
  }, [documentsQuery.data?.pages]);

  // Reset stream + buffers when the list query key changes (filters/sort/search/pageSize/workspace)
  useEffect(() => {
    setChangesCursor(null);
    changesCursorRef.current = null;
    lastChangeCursorRef.current = null;

    pendingChangesRef.current = [];
    changeStreamControllerRef.current?.abort();

    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, [listKey]);

  // Stop SSE if change detection disabled
  useEffect(() => {
    if (!changeDetectionEnabled) {
      changeStreamControllerRef.current?.abort();
      pendingChangesRef.current = [];
      lastChangeCursorRef.current = null;
      if (flushTimerRef.current) {
        window.clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    }
  }, [changeDetectionEnabled]);

  // Refresh first page (coalesced)
  const refreshDocumentsFirstPage = useCallback(async () => {
    if (!workspaceId) return;
    if (refreshInFlightRef.current) {
      refreshQueuedRef.current = true;
      return;
    }

    refreshInFlightRef.current = true;
    try {
      const page = await fetchWorkspaceDocuments(workspaceId, {
        sort,
        page: 1,
        perPage: listSettings.pageSize,
        filters: filterItems,
        q,
      });

      queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
        if (!existing) return existing;
        return {
          ...existing,
          pages: [page],
          pageParams: existing.pageParams.length > 0 ? [existing.pageParams[0]] : [1],
        };
      });
    } catch (error) {
      console.warn("Document refresh failed", error);
    } finally {
      refreshInFlightRef.current = false;
      if (refreshQueuedRef.current) {
        refreshQueuedRef.current = false;
        void refreshDocumentsFirstPage();
      }
    }
  }, [filterItems, listKey, listSettings.pageSize, q, queryClient, sort, workspaceId]);

  const scheduleDocumentsRefresh = useCallback(() => {
    if (refreshTimerRef.current) return;
    refreshTimerRef.current = window.setTimeout(() => {
      refreshTimerRef.current = null;
      void refreshDocumentsFirstPage();
    }, 500);
  }, [refreshDocumentsFirstPage]);

  // Flush batched changes into query cache
  const flushPendingChanges = useCallback(() => {
    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
    }
    flushTimerRef.current = null;

    const batch = compactDocumentChanges(pendingChangesRef.current.splice(0));
    if (batch.length === 0) return;

    let shouldRefresh = false;

    queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
      if (!existing) return existing;

      let data = existing;
      for (const change of batch) {
        const result = mergeDocumentChangeIntoPages(data, change);
        data = result.data;
        if (result.updatesAvailable) shouldRefresh = true;
      }
      return data;
    });

    // Keep per-document row cache hot for pinned/preview
    for (const change of batch) {
      if (change.type === "document.upsert" && change.row) {
        queryClient.setQueryData(documentsKeys.document(workspaceId, change.row.id), change.row);
      }
      if (change.type === "document.deleted" && change.documentId) {
        queryClient.removeQueries({ queryKey: documentsKeys.document(workspaceId, change.documentId) });
      }
    }

    if (shouldRefresh) scheduleDocumentsRefresh();
  }, [listKey, queryClient, scheduleDocumentsRefresh, workspaceId]);

  const enqueueChange = useCallback(
    (change: DocumentChangeEntry) => {
      pendingChangesRef.current.push(change);
      if (flushTimerRef.current) return;
      flushTimerRef.current = window.setTimeout(() => flushPendingChanges(), 200);
    },
    [flushPendingChanges],
  );

  // Main SSE stream: durable cursor feed (single connection)
  useEffect(() => {
    if (!workspaceId || !changesCursor || !changeDetectionEnabled) return;

    changeStreamControllerRef.current?.abort();
    pendingChangesRef.current = [];
    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }

    const controller = new AbortController();
    changeStreamControllerRef.current = controller;

    const sleep = (duration: number) =>
      new Promise<void>((resolve) => {
        let timeout: number;
        const handleAbort = () => {
          window.clearTimeout(timeout);
          controller.signal.removeEventListener("abort", handleAbort);
          resolve();
        };
        timeout = window.setTimeout(() => {
          controller.signal.removeEventListener("abort", handleAbort);
          resolve();
        }, duration);
        controller.signal.addEventListener("abort", handleAbort);
      });

    void (async () => {
      let retryAttempt = 0;

      while (!controller.signal.aborted) {
        const cursor = lastChangeCursorRef.current ?? changesCursor;
        const streamUrl = documentChangesStreamUrl(workspaceId, {
          cursor,
          sort,
          q: q ?? undefined,
          filters: filterItems,
        });

        try {
          for await (const change of streamDocumentChanges(streamUrl, controller.signal)) {
            lastChangeCursorRef.current = change.cursor;
            enqueueChange(change);
            retryAttempt = 0;
          }
        } catch (error) {
          if (controller.signal.aborted) return;

          // Cursor too old, server requests a resync.
          if (error instanceof ApiError && error.status === 410) {
            void refetchDocuments();
            return;
          }

          console.warn("Document change stream failed", error);
        }

        if (controller.signal.aborted) return;

        // Exponential backoff with jitter
        const baseDelay = 1000;
        const maxDelay = 30000;
        const delay = Math.min(maxDelay, baseDelay * 2 ** Math.min(retryAttempt, 5));
        retryAttempt += 1;
        const jitter = Math.floor(delay * 0.15 * Math.random());
        await sleep(delay + jitter);
      }
    })();

    return () => controller.abort();
  }, [changeDetectionEnabled, changesCursor, enqueueChange, filterItems, q, refetchDocuments, sort, workspaceId]);

  // Upload notifications
  useEffect(() => {
    uploadManager.items.forEach((item) => {
      if (item.status === "succeeded" && item.response && !handledUploadsRef.current.has(item.id)) {
        handledUploadsRef.current.add(item.id);
      }
      if (item.status === "failed" && item.error && !handledUploadsRef.current.has(`fail-${item.id}`)) {
        handledUploadsRef.current.add(`fail-${item.id}`);
        notifyToast({ title: "Upload failed", description: item.error, intent: "danger" });
      }
    });
  }, [notifyToast, uploadManager.items]);

  // Periodically refetch configurations if missing
  useEffect(() => {
    if (!configMissing) return;
    const interval = window.setInterval(() => void refetchConfigurations(), 10000);
    return () => window.clearInterval(interval);
  }, [configMissing, refetchConfigurations]);

  // Map upload IDs -> real doc IDs once server responds, and migrate selection/active/anchor
  useEffect(() => {
    const uploadIdsSet = new Set(uploadManager.items.map((i) => i.id));

    let hasMapping = false;
    uploadManager.items.forEach((item) => {
      if (item.status === "succeeded" && item.response?.id) {
        uploadIdMapRef.current.set(item.id, item.response.id);
        hasMapping = true;
      }
    });

    if (!hasMapping) return;

    setSelectedIds((prev) => {
      let next: Set<string> | null = null;
      uploadIdMapRef.current.forEach((docId, uploadId) => {
        if (!prev.has(uploadId)) return;
        if (!next) next = new Set(prev);
        next.delete(uploadId);
        next.add(docId);
      });
      return next ?? prev;
    });

    setActiveId((prev) => {
      if (!prev) return prev;
      const mapped = uploadIdMapRef.current.get(prev);
      // If activeId is still a live upload id, keep it until it maps.
      if (uploadIdsSet.has(prev) && !mapped) return prev;
      return mapped ?? prev;
    });

    const anchor = selectionAnchorRef.current;
    if (anchor && uploadIdMapRef.current.has(anchor)) {
      selectionAnchorRef.current = uploadIdMapRef.current.get(anchor) ?? anchor;
    }
  }, [uploadManager.items]);

  // Build upload entries (optimistic rows)
  const uploadEntries = useMemo(() => {
    const entries: DocumentEntry[] = [];

    uploadManager.items.forEach((item) => {
      const createdAt = uploadCreatedAtRef.current.get(item.id) ?? Date.now();
      const fileName = item.file.name;

      // If the upload succeeded and the server row is already present, hide the optimistic row.
      if (item.status === "succeeded" && item.response?.id && documentIdsSet.has(item.response.id)) return;

      const status: DocumentStatus = item.status === "failed" ? "failed" : "uploaded";
      const timestamp = new Date(createdAt).toISOString();

      entries.push({
        id: item.id,
        workspaceId: workspaceId,
        name: fileName,
        status,
        fileType: fileTypeFromName(fileName),
        uploader: {
          id: currentUserId,
          name: currentUserLabel,
          email: currentUserEmail,
        },
        assignee: null,
        assigneeKey: null,
        uploaderLabel: currentUserLabel,
        tags: [],
        byteSize: item.file.size,
        createdAt: timestamp,
        updatedAt: timestamp,
        activityAt: timestamp,
        latestRun: null,
        latestSuccessfulRun: null,
        latestResult: { attention: 0, unmapped: 0, pending: true },
        progress: item.status === "uploading" ? item.progress.percent : undefined,
        error:
          item.status === "failed"
            ? {
                summary: item.error ?? "Upload failed",
                detail: "We could not upload this file. Check the connection and retry.",
                nextStep: "Retry now or remove the upload.",
              }
            : undefined,
        assigneeLabel: null,
        commentCount: (commentsByDocId[item.id] ?? []).length,
        upload: item,
      });
    });

    return entries;
  }, [commentsByDocId, currentUserEmail, currentUserId, currentUserLabel, documentIdsSet, uploadManager.items, workspaceId]);

  const uploadIdsSet = useMemo(() => new Set(uploadManager.items.map((i) => i.id)), [uploadManager.items]);
  const activeIdIsUpload = useMemo(() => Boolean(activeId && uploadIdsSet.has(activeId)), [activeId, uploadIdsSet]);

  // People
  const membersQuery = useQuery({
    queryKey: documentsKeys.members(workspaceId),
    queryFn: ({ signal }) => listWorkspaceMembers(workspaceId, { signal }),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const people = useMemo<WorkspacePerson[]>(() => {
    const set = new Map<string, WorkspacePerson>();
    set.set(currentUserKey, { key: currentUserKey, label: currentUserLabel, kind: "user", userId: currentUserId });

    const members = membersQuery.data?.items ?? [];
    members.forEach((m) => {
      const key = `user:${m.user_id}`;
      const label = m.user_id === currentUserId ? currentUserLabel : `Member ${shortId(m.user_id)}`;
      if (!set.has(key)) set.set(key, { key, label, kind: "user", userId: m.user_id });
    });

    return Array.from(set.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [currentUserId, currentUserKey, currentUserLabel, membersQuery.data?.items]);

  const peopleByKey = useMemo(() => new Map(people.map((p) => [p.key, p])), [people]);

  const assigneeLabelForKey = useCallback(
    (key: string | null) => {
      if (!key) return null;
      const found = peopleByKey.get(key);
      if (found) return found.label;
      if (key.startsWith("user:")) return `Member ${shortId(key.slice(5))}`;
      if (key.startsWith("label:")) return key.slice(6);
      return key;
    },
    [peopleByKey],
  );

  // Fetch row for active doc if it's not in loaded pages (and not an optimistic upload)
  const activeRowQuery = useQuery({
    queryKey:
      activeId && workspaceId ? documentsKeys.document(workspaceId, activeId) : [...documentsKeys.root(), "document", "none"],
    queryFn: ({ signal }) => (activeId ? fetchWorkspaceDocumentRowById(workspaceId, activeId, signal) : Promise.reject()),
    enabled: Boolean(activeId && workspaceId) && !documentIdsSet.has(activeId ?? "") && !activeIdIsUpload,
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });

  // Wrap API rows into DocumentEntry with stable identity when unchanged.
  const apiEntries = useMemo(() => {
    const cache = apiEntryCacheRef.current;
    const keepIds = new Set<string>();

    const result: DocumentEntry[] = [];

    for (const row of documentsRaw) {
      keepIds.add(row.id);

      const assigneeKey = row.assignee?.id ? `user:${row.assignee.id}` : null;
      const commentCount = (commentsByDocId[row.id] ?? []).length;
      const assigneeLabel = assigneeLabelForKey(assigneeKey);
      const uploaderLabel = row.uploader?.name || row.uploader?.email || null;

      const cached = cache.get(row.id);
      if (
        cached &&
        cached.row === row &&
        cached.assigneeKey === assigneeKey &&
        cached.commentCount === commentCount &&
        cached.assigneeLabel === assigneeLabel &&
        cached.uploaderLabel === uploaderLabel
      ) {
        result.push(cached.entry);
        continue;
      }

      const entry: DocumentEntry = {
        ...row,
        record: row,
        assigneeKey: assigneeKey,
        assigneeLabel: assigneeLabel,
        uploaderLabel,
        commentCount: commentCount,
        tags: row.tags ?? [],
      };

      cache.set(row.id, { row, assigneeKey, assigneeLabel, uploaderLabel, commentCount, entry });
      result.push(entry);
    }

    // Prune cache (prevents memory growth). Keep active pinned row if present.
    const pinnedRowId = activeRowQuery.data?.id ?? null;
    if (pinnedRowId) keepIds.add(pinnedRowId);

    for (const id of Array.from(cache.keys())) {
      if (!keepIds.has(id)) cache.delete(id);
    }

    return result;
  }, [assigneeLabelForKey, commentsByDocId, documentsRaw, activeRowQuery.data?.id]);

  const pinnedActiveEntry = useMemo(() => {
    if (!activeRowQuery.data) return null;

    const row = activeRowQuery.data;
    const assigneeKey = row.assignee?.id ? `user:${row.assignee.id}` : null;
    const commentCount = (commentsByDocId[row.id] ?? []).length;
    const uploaderLabel = row.uploader?.name || row.uploader?.email || null;

    const entry: DocumentEntry = {
      ...row,
      record: row,
      assigneeKey: assigneeKey,
      assigneeLabel: assigneeLabelForKey(assigneeKey),
      uploaderLabel,
      commentCount: commentCount,
      tags: row.tags ?? [],
    };

    return entry;
  }, [activeRowQuery.data, assigneeLabelForKey, commentsByDocId]);

  const filteredUploadEntries = useMemo(
    () => filterUploadEntries(uploadEntries, filters, search),
    [filters, search, uploadEntries],
  );

  const documents = useMemo(() => {
    const all = [...filteredUploadEntries, ...apiEntries];
    if (pinnedActiveEntry && !all.some((d) => d.id === pinnedActiveEntry.id)) {
      return [pinnedActiveEntry, ...all];
    }
    return all;
  }, [apiEntries, filteredUploadEntries, pinnedActiveEntry]);

  const documentsByEntryId = useMemo(() => new Map(documents.map((d) => [d.id, d])), [documents]);

  // Ensure there is always an active row when documents exist.
  useEffect(() => {
    if (documents.length === 0) {
      setActiveId(null);
      return;
    }
    if (!activeId || !documentsByEntryId.has(activeId)) {
      setActiveId(documents[0].id);
    }
  }, [activeId, documents, documentsByEntryId]);

  const activeDocument = useMemo(
    () => (activeId ? documentsByEntryId.get(activeId) ?? null : null),
    [activeId, documentsByEntryId],
  );

  const visibleDocuments = documents;

  // Board columns are expensive; compute only when board view is active.
  const boardColumns = useMemo<BoardColumn[]>(() => {
    if (viewMode !== "board") return [];

    if (groupBy === "status") {
      return STATUS_ORDER.map((status) => ({
        id: status,
        label: statusLabel(status),
        items: visibleDocuments.filter((doc) => doc.status === status),
      }));
    }

    if (groupBy === "tag") {
      const tagSet = new Set<string>();
      visibleDocuments.forEach((doc) => doc.tags.forEach((tag) => tagSet.add(tag)));
      const tags = Array.from(tagSet).sort((a, b) => a.localeCompare(b));

      const columns = tags.map((tag) => ({
        id: tag,
        label: tag,
        items: visibleDocuments.filter((doc) => doc.tags.includes(tag)),
      }));

      columns.push({
        id: "__untagged__",
        label: "Untagged",
        items: visibleDocuments.filter((doc) => doc.tags.length === 0),
      });

      return columns;
    }

    const uploaderSet = new Set<string>();
    visibleDocuments.forEach((doc) => {
      if (doc.uploaderLabel) uploaderSet.add(doc.uploaderLabel);
    });

    const uploaders = Array.from(uploaderSet).sort((a, b) => a.localeCompare(b));

    const columns = uploaders.map((uploader) => ({
      id: uploader,
      label: uploader,
      items: visibleDocuments.filter((doc) => doc.uploaderLabel === uploader),
    }));

    columns.push({
      id: "__unassigned_uploader__",
      label: "Unassigned",
      items: visibleDocuments.filter((doc) => !doc.uploaderLabel),
    });

    return columns;
  }, [groupBy, visibleDocuments, viewMode]);

  // Selection helpers
  const selectableIds = useMemo(() => visibleDocuments.filter((doc) => doc.record).map((doc) => doc.id), [visibleDocuments]);
  const selectableIndexById = useMemo(() => {
    const map = new Map<string, number>();
    selectableIds.forEach((id, idx) => map.set(id, idx));
    return map;
  }, [selectableIds]);

  const selectedDocumentIds = useMemo(() => {
    return documents.filter((doc) => selectedIds.has(doc.id) && doc.record).map((doc) => doc.id);
  }, [documents, selectedIds]);

  const visibleSelectedCount = useMemo(() => selectableIds.filter((id) => selectedIds.has(id)).length, [selectableIds, selectedIds]);
  const allVisibleSelected = selectableIds.length > 0 && visibleSelectedCount === selectableIds.length;
  const someVisibleSelected = visibleSelectedCount > 0 && !allVisibleSelected;

  // Prune selection when visible selectable IDs change.
  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      selectableIds.forEach((id) => {
        if (previous.has(id)) next.add(id);
      });
      if (next.size === previous.size) return previous;
      return next;
    });

    if (selectionAnchorRef.current && !selectableIndexById.has(selectionAnchorRef.current)) {
      selectionAnchorRef.current = null;
    }
  }, [selectableIds, selectableIndexById]);

  const hasActiveFilters =
    search.trim().length >= 2 ||
    filters.statuses.length > 0 ||
    filters.fileTypes.length > 0 ||
    filters.tags.length > 0 ||
    filters.assignees.length > 0;

  const showNoDocuments = documents.length === 0 && !hasActiveFilters;
  const showNoResults = documents.length === 0 && hasActiveFilters;

  const lastUpdatedAt = documentsQuery.dataUpdatedAt > 0 ? documentsQuery.dataUpdatedAt : null;
  const isRefreshing = documentsQuery.isFetching && Boolean(documentsQuery.data);

  // Counts in a single pass (fast for large lists)
  const counts = useMemo(() => {
    let assignedToMe = 0;
    let unassigned = 0;
    let assignedToMeOrUnassigned = 0;
    let active = 0;
    let processed = 0;
    let processing = 0;
    let failed = 0;
    let archived = 0;

    for (const d of documents) {
      const isMine = d.assigneeKey === currentUserKey;
      const isUnassigned = !d.assigneeKey;

      if (isMine) assignedToMe += 1;
      if (isUnassigned) unassigned += 1;
      if (isMine || isUnassigned) assignedToMeOrUnassigned += 1;

      if (ACTIVE_DOCUMENT_STATUSES.includes(d.status)) active += 1;

      if (d.status === "processed") processed += 1;
      if (d.status === "processing" || d.status === "uploaded") processing += 1;
      if (d.status === "failed") failed += 1;
      if (d.status === "archived") archived += 1;
    }

    return {
      total: documents.length,
      active,
      assignedToMe,
      assignedToMeOrUnassigned,
      unassigned,
      processed,
      processing,
      failed,
      archived,
    };
  }, [currentUserKey, documents]);

  const activeComments = useMemo(() => {
    if (!activeDocument) return [];
    return commentsByDocId[activeDocument.id] ?? [];
  }, [activeDocument, commentsByDocId]);

  // Runs in preview: query runs for active doc only when preview is open.
  const activeDocumentIdForRuns = activeDocument?.record?.id ?? null;

  const runsQuery = useQuery({
    queryKey: activeDocumentIdForRuns
      ? documentsKeys.runsForDocument(workspaceId, activeDocumentIdForRuns)
      : [...documentsKeys.workspace(workspaceId), "runs", "none"],
    queryFn: ({ signal }) =>
      activeDocumentIdForRuns ? fetchWorkspaceRunsForDocument(workspaceId, activeDocumentIdForRuns, signal) : Promise.resolve([]),
    enabled: Boolean(activeDocumentIdForRuns) && previewOpen,
    staleTime: 5_000,
    refetchInterval: previewOpen ? 7_500 : false,
  });

  const runs = useMemo(() => {
    const items = runsQuery.data ?? [];
    return items.slice().sort((a, b) => parseTimestamp(b.createdAt) - parseTimestamp(a.createdAt));
  }, [runsQuery.data]);

  const preferredRunId = activeDocument?.record?.latestRun?.id ?? null;

  useEffect(() => {
    if (!previewOpen) return;
    setSelectedRunId((prev) => {
      const existing = prev && runs.some((r) => r.id === prev) ? prev : null;
      if (existing) return existing;
      if (preferredRunId && runs.some((r) => r.id === preferredRunId)) return preferredRunId;
      return runs[0]?.id ?? null;
    });
  }, [preferredRunId, previewOpen, runs]);

  const activeRun = useMemo(() => {
    if (!selectedRunId) return null;
    return runs.find((r) => r.id === selectedRunId) ?? null;
  }, [runs, selectedRunId]);

  const shouldPollRunMetrics = previewOpen && activeRun ? activeRun.status === "running" || activeRun.status === "queued" : false;

  const runMetricsQuery = useQuery({
    queryKey: selectedRunId ? documentsKeys.runMetrics(selectedRunId) : [...documentsKeys.root(), "runMetrics", "none"],
    queryFn: ({ signal }) => (selectedRunId ? fetchRunMetrics(selectedRunId, signal) : Promise.resolve(null)),
    enabled: Boolean(selectedRunId) && previewOpen,
    staleTime: 30_000,
    refetchInterval: shouldPollRunMetrics ? 10_000 : false,
  });

  const outputUrl = useMemo(() => {
    if (!activeRun) return null;
    if (!runHasDownloadableOutput(activeRun)) return null;
    return runOutputDownloadUrl(activeRun);
  }, [activeRun]);

  const workbookQuery = useQuery<WorkbookPreview>({
    queryKey: outputUrl ? documentsKeys.workbook(outputUrl) : [...documentsKeys.root(), "workbook", "none"],
    queryFn: ({ signal }) =>
      outputUrl ? fetchWorkbookPreview(outputUrl, signal) : Promise.reject(new Error("No output URL")),
    enabled: Boolean(outputUrl) && previewOpen,
    staleTime: 30_000,
  });

  useEffect(() => {
    setActiveSheetId(null);
  }, [activeDocument?.id, selectedRunId]);

  useEffect(() => {
    if (workbookQuery.data?.sheets.length) setActiveSheetId(workbookQuery.data.sheets[0].name);
  }, [workbookQuery.data?.sheets]);

  // View id resolution
  const resolveViewId = useCallback(
    (nextFilters: DocumentsFilters, nextSearch: string) => resolveActiveViewId(nextFilters, nextSearch, savedViews, currentUserKey),
    [currentUserKey, savedViews],
  );

  const setSearchValue = useCallback(
    (value: string) => {
      setSearch(value);
      setActiveViewId(resolveViewId(filters, value));
    },
    [filters, resolveViewId],
  );

  const setViewModeValue = useCallback((value: ViewMode) => setViewMode(value), []);
  const setGroupByValue = useCallback((value: BoardGroup) => setGroupBy(value), []);

  // Selection
  const updateSelection = useCallback(
    (id: string, options?: { mode?: "toggle" | "range"; checked?: boolean }) => {
      const isRange = options?.mode === "range" || shiftPressedRef.current;

      setSelectedIds((previous) => {
        const next = new Set(previous);
        const shouldSelect = isRange ? options?.checked ?? true : options?.checked ?? !previous.has(id);

        const anchorId = selectionAnchorRef.current;
        if (isRange && anchorId) {
          const startIndex = selectableIndexById.get(anchorId);
          const endIndex = selectableIndexById.get(id);

          if (startIndex !== undefined && endIndex !== undefined) {
            const [from, to] = startIndex < endIndex ? [startIndex, endIndex] : [endIndex, startIndex];
            for (let i = from; i <= to; i += 1) {
              const targetId = selectableIds[i];
              if (shouldSelect) next.add(targetId);
              else next.delete(targetId);
            }
            return next;
          }
        }

        if (shouldSelect) next.add(id);
        else next.delete(id);
        return next;
      });

      if (!isRange || !selectionAnchorRef.current) selectionAnchorRef.current = id;
    },
    [selectableIds, selectableIndexById],
  );

  const selectAllVisible = useCallback(() => setSelectedIds(new Set(selectableIds)), [selectableIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
    selectionAnchorRef.current = null;
  }, []);

  // Preview
  const openPreview = useCallback((id: string) => {
    selectionAnchorRef.current = id;
    setActiveId(id);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => setPreviewOpen(false), []);
  const setActiveSheetIdValue = useCallback((id: string) => setActiveSheetId(id), []);

  // Upload management
  const queueUploads = useCallback(
    (items: UploadManagerQueueItem[]) => {
      if (!items.length) return;

      const nextItems = uploadManager.enqueue(items);

      const nowTimestamp = Date.now();
      nextItems.forEach((item, index) => {
        uploadCreatedAtRef.current.set(item.id, nowTimestamp + index * 1000);
      });

      const description = processingPaused
        ? configMissing
          ? "Uploads saved. Processing is paused and no configuration is active yet."
          : "Uploads saved. Processing is paused for this workspace."
        : configMissing
          ? "Uploads saved. Processing will start once an active configuration is set."
          : "Processing will begin automatically.";

      notifyToast({
        title: `${nextItems.length} file${nextItems.length === 1 ? "" : "s"} added`,
        description,
        intent: "success",
      });
    },
    [configMissing, notifyToast, processingPaused, uploadManager],
  );

  const handleUploadClick = useCallback(() => fileInputRef.current?.click(), []);
  const pauseUpload = useCallback((uploadId: string) => uploadManager.pause(uploadId), [uploadManager]);
  const resumeUpload = useCallback((uploadId: string) => uploadManager.resume(uploadId), [uploadManager]);
  const retryUpload = useCallback((uploadId: string) => uploadManager.retry(uploadId), [uploadManager]);
  const cancelUpload = useCallback((uploadId: string) => uploadManager.cancel(uploadId), [uploadManager]);
  const removeUpload = useCallback((uploadId: string) => uploadManager.remove(uploadId), [uploadManager]);
  const clearCompletedUploads = useCallback(() => uploadManager.clearCompleted(), [uploadManager]);

  const refreshDocuments = useCallback(() => void documentsQuery.refetch(), [documentsQuery]);
  const loadMore = useCallback(() => {
    if (documentsQuery.hasNextPage) void documentsQuery.fetchNextPage();
  }, [documentsQuery]);

  // Keyboard navigation
  const visibleIndexById = useMemo(() => {
    const map = new Map<string, number>();
    visibleDocuments.forEach((doc, idx) => map.set(doc.id, idx));
    return map;
  }, [visibleDocuments]);

  const handleKeyNavigate = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, button, a, [role='button'], [role='menuitem']")) return;

      if (visibleDocuments.length === 0) return;
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

      event.preventDefault();

      const currentIndex = activeId ? visibleIndexById.get(activeId) ?? -1 : -1;
      if (currentIndex < 0) {
        setActiveId(visibleDocuments[0].id);
        return;
      }

      const nextIndex =
        event.key === "ArrowDown"
          ? Math.min(visibleDocuments.length - 1, currentIndex + 1)
          : Math.max(0, currentIndex - 1);

      setActiveId(visibleDocuments[nextIndex].id);
    },
    [activeId, visibleDocuments, visibleIndexById],
  );

  // Filters & views
  const setFiltersValue = useCallback(
    (next: DocumentsFilters) => {
      setFilters(next);
      setActiveViewId(resolveViewId(next, search));
    },
    [resolveViewId, search],
  );

  const setListSettingsValue = useCallback((next: ListSettings) => setListSettings(normalizeListSettings(next)), []);

  const setBuiltInView = useCallback(
    (id: BuiltInViewId) => {
      setActiveViewId(id);
      setFilters(buildFiltersForBuiltInView(id, currentUserKey));
    },
    [currentUserKey],
  );

  const selectSavedView = useCallback(
    (viewId: string) => {
      const view = savedViews.find((v) => v.id === viewId);
      if (!view) return;
      setFilters(view.filters);
      setActiveViewId(viewId);
    },
    [savedViews],
  );

  const openSaveView = useCallback(() => setSaveViewOpen(true), []);
  const closeSaveView = useCallback(() => setSaveViewOpen(false), []);

  const saveView = useCallback(
    (name: string) => {
      const timestamp = Date.now();
      const view: SavedView = {
        id: `view_${timestamp}`,
        name,
        createdAt: timestamp,
        updatedAt: timestamp,
        filters,
      };
      const next = [view, ...savedViews];
      setSavedViews(next);
      storeSavedViews(workspaceId, next);
      setActiveViewId(view.id);
      notifyToast({ title: "View saved", description: name, intent: "success" });
    },
    [filters, notifyToast, savedViews, workspaceId],
  );

  const deleteView = useCallback(
    (viewId: string) => {
      const next = savedViews.filter((v) => v.id !== viewId);
      setSavedViews(next);
      storeSavedViews(workspaceId, next);
      if (activeViewId === viewId) setActiveViewId("all_documents");
      notifyToast({ title: "View deleted", description: viewId, intent: "success" });
    },
    [activeViewId, notifyToast, savedViews, workspaceId],
  );

  // Tags (persisted)
  const updateTagsOptimistic = useCallback(
    (documentId: string, nextTags: string[]) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;

      const prevTags = entry.tags;
      const add = nextTags.filter((tag) => !prevTags.includes(tag));
      const remove = prevTags.filter((tag) => !nextTags.includes(tag));
      if (add.length === 0 && remove.length === 0) return;

      void patchDocumentTags(workspaceId, entry.id, { add, remove })
        .then(() => {
          queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
            if (!existing?.pages) return existing;
            return {
              ...existing,
              pages: existing.pages.map((page) => ({
                ...page,
                items: (page.items ?? []).map((item) => (item.id === entry.id ? { ...item, tags: nextTags } : item)),
              })),
            };
          });

          queryClient.setQueryData(documentsKeys.document(workspaceId, entry.id), (existing: DocumentEntry | undefined) =>
            existing ? { ...existing, tags: nextTags } : existing,
          );
        })
        .catch((error) => {
          notifyToast({
            title: "Tag update failed",
            description: error instanceof Error ? error.message : "Unable to update tags.",
            intent: "danger",
          });
        });
    },
    [documentsByEntryId, listKey, notifyToast, queryClient, workspaceId],
  );

  // Assignment
  const assignDocument = useCallback(
    (documentId: string, assigneeKey: string | null) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;

      const assigneeId = assigneeKey?.startsWith("user:") ? assigneeKey.slice(5) : null;
      const assigneeLabel = assigneeKey ? (peopleByKey.get(assigneeKey)?.label ?? assigneeKey) : null;
      const assigneeEmail = assigneeLabel && assigneeLabel.includes("@") ? assigneeLabel : "";
      const assigneeSummary = assigneeId
        ? {
            id: assigneeId,
            name: assigneeLabel ?? assigneeId,
            email: assigneeEmail,
          }
        : null;

      const ifMatch = buildWeakEtag(entry.id, entry.updatedAt);
      void patchWorkspaceDocument(workspaceId, entry.id, { assigneeId }, { ifMatch })
        .then(() => {
          queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
            if (!existing?.pages) return existing;
            return {
              ...existing,
              pages: existing.pages.map((page) => ({
                ...page,
                items: (page.items ?? []).map((item) =>
                  item.id === entry.id ? { ...item, assignee: assigneeSummary } : item,
                ),
              })),
            };
          });

          queryClient.setQueryData(documentsKeys.document(workspaceId, entry.id), (existing: DocumentEntry | undefined) =>
            existing
              ? {
                  ...existing,
                  assignee: assigneeSummary,
                  assigneeKey: assigneeKey,
                  assigneeLabel: assigneeLabelForKey(assigneeKey),
                }
              : existing,
          );

          notifyToast({
            title: "Assignment updated",
            description: assigneeLabel ?? "Unassigned",
            intent: "success",
          });
        })
        .catch((error) => {
          notifyToast({
            title: "Assignment failed",
            description: error instanceof Error ? error.message : "Unable to update assignment.",
            intent: "danger",
          });
        });
    },
    [assigneeLabelForKey, documentsByEntryId, listKey, notifyToast, peopleByKey, queryClient, workspaceId],
  );

  const pickUpDocument = useCallback((documentId: string) => assignDocument(documentId, currentUserKey), [assignDocument, currentUserKey]);

  // Notes (local-first)
  const addComment = useCallback(
    (documentId: string, body: string, mentions: { key: string; label: string }[]) => {
      const timestamp = Date.now();
      const comment: DocumentComment = {
        id: `c_${timestamp}_${Math.random().toString(16).slice(2)}`,
        documentId,
        authorKey: currentUserKey,
        authorLabel: currentUserLabel,
        body,
        createdAt: timestamp,
        updatedAt: timestamp,
        mentions,
      };

      setCommentsByDocId((prev) => {
        const nextList = [...(prev[documentId] ?? []), comment];
        const next = { ...prev, [documentId]: nextList };
        storeComments(workspaceId, next);
        return next;
      });

      notifyToast({ title: "Note added", description: "Saved locally for now.", intent: "success" });
    },
    [currentUserKey, currentUserLabel, notifyToast, workspaceId],
  );

  const editComment = useCallback(
    (documentId: string, commentId: string, body: string, mentions: { key: string; label: string }[]) => {
      setCommentsByDocId((prev) => {
        const list = prev[documentId] ?? [];
        const nextList = list.map((c) => (c.id === commentId ? { ...c, body, mentions, updatedAt: Date.now() } : c));
        const next = { ...prev, [documentId]: nextList };
        storeComments(workspaceId, next);
        return next;
      });
      notifyToast({ title: "Note updated", description: "Saved locally for now.", intent: "success" });
    },
    [notifyToast, workspaceId],
  );

  const deleteComment = useCallback(
    (documentId: string, commentId: string) => {
      setCommentsByDocId((prev) => {
        const list = prev[documentId] ?? [];
        const nextList = list.filter((c) => c.id !== commentId);
        const next = { ...prev, [documentId]: nextList };
        storeComments(workspaceId, next);
        return next;
      });
      notifyToast({ title: "Note deleted", description: "Removed locally for now.", intent: "success" });
    },
    [notifyToast, workspaceId],
  );

  // Runs
  const selectRun = useCallback((runId: string) => setSelectedRunId(runId), []);

  // Downloads
  const downloadOutput = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record) return;

      if (!outputUrl) {
        notifyToast({
          title: "No output link",
          description: "We could not find the output download link yet.",
          intent: "warning",
        });
        return;
      }

      void downloadRunOutput(outputUrl, doc.name)
        .then((filename) => notifyToast({ title: "Download started", description: filename, intent: "success" }))
        .catch((error) =>
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download the processed XLSX.",
            intent: "danger",
          }),
        );
    },
    [notifyToast, outputUrl],
  );

  const downloadOutputFromRow = useCallback(
    (doc: DocumentEntry) => {
      const runId = getDocumentOutputRun(doc.record)?.id ?? null;
      if (!doc.record || !runId) {
        notifyToast({
          title: "Output not ready",
          description: "Open the document to see run history and download output.",
          intent: "warning",
        });
        return;
      }
      void downloadRunOutputById(runId, doc.name)
        .then((filename) => notifyToast({ title: "Download started", description: filename, intent: "success" }))
        .catch((error) =>
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download the processed XLSX.",
            intent: "danger",
          }),
        );
    },
    [notifyToast],
  );

  const downloadOriginal = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record) return;
      void downloadOriginalDocument(workspaceId, doc.id, doc.name)
        .then((filename) => notifyToast({ title: "Download started", description: filename, intent: "success" }))
        .catch((error) =>
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download the original file.",
            intent: "danger",
          }),
        );
    },
    [notifyToast, workspaceId],
  );

  // Reprocess
  const reprocess = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record) return;

      if (processingPaused) {
        notifyToast({
          title: "Processing is paused",
          description: "Resume processing in workspace settings to reprocess documents.",
          intent: "warning",
        });
        return;
      }

      if (!activeRun?.configuration_id) {
        notifyToast({
          title: "Cannot reprocess yet",
          description: "No configuration is available for this document's runs yet.",
          intent: "warning",
        });
        return;
      }

      void createRunForDocument(activeRun.configuration_id, doc.id)
        .then((created) => {
          notifyToast({ title: "Reprocess queued", description: `Run ${shortId(created.id)}`, intent: "success" });
          // No list invalidation: the change feed will update the row as runs start/complete.
        })
        .catch((error) =>
          notifyToast({
            title: "Reprocess failed",
            description: error instanceof Error ? error.message : "Unable to reprocess.",
            intent: "danger",
          }),
        );
    },
    [activeRun?.configuration_id, notifyToast, processingPaused],
  );

  // Copy link
  const copyLink = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record) return;
      const url = new URL(window.location.href);
      url.searchParams.set("doc", doc.id);

      void copyToClipboard(url.toString())
        .then(() => notifyToast({ title: "Link copied", description: "Share it with your team.", intent: "success" }))
        .catch(() => notifyToast({ title: "Copy failed", description: "Unable to copy link to clipboard.", intent: "danger" }));
    },
    [notifyToast],
  );

  // Helpers for safe cache removal without full invalidation
  const removeIdsFromSelection = useCallback((ids: string[]) => {
    if (ids.length === 0) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.delete(id));
      return next;
    });
  }, []);

  const removeFromListCache = useCallback(
    (ids: string[]) => {
      if (ids.length === 0) return;
      const removeSet = new Set(ids);

      queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
        if (!existing?.pages) return existing;
        return {
          ...existing,
          pages: existing.pages.map((page) => ({
            ...page,
            items: (page.items ?? []).filter((item) => !removeSet.has(item.id)),
          })),
        };
      });
    },
    [listKey, queryClient],
  );

  // Delete / archive / restore (single) — no workspace invalidation.
  const deleteDocument = useCallback(
    (documentId: string) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;

      const ifMatch = buildWeakEtag(entry.id, entry.updatedAt);
      void deleteWorkspaceDocument(workspaceId, entry.id, { ifMatch })
        .then(() => {
          notifyToast({ title: "Document deleted", description: entry.name, intent: "success" });

          removeFromListCache([entry.id]);
          queryClient.removeQueries({ queryKey: documentsKeys.document(workspaceId, entry.id) });
          removeIdsFromSelection([entry.id]);
        })
        .catch((error) =>
          notifyToast({
            title: "Delete failed",
            description: error instanceof Error ? error.message : "Unable to delete document.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, removeFromListCache, removeIdsFromSelection, workspaceId],
  );

  const archiveDocument = useCallback(
    (documentId: string) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;

      void archiveWorkspaceDocument(workspaceId, entry.id)
        .then(() => {
          notifyToast({ title: "Document archived", description: entry.name, intent: "success" });
          // Let the SSE feed apply the authoritative status update.
          removeIdsFromSelection([entry.id]);
        })
        .catch((error) =>
          notifyToast({
            title: "Archive failed",
            description: error instanceof Error ? error.message : "Unable to archive document.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, removeIdsFromSelection, workspaceId],
  );

  const restoreDocument = useCallback(
    (documentId: string) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;

      void restoreWorkspaceDocument(workspaceId, entry.id)
        .then(() => {
          notifyToast({ title: "Document restored", description: entry.name, intent: "success" });
          // Let the SSE feed apply the authoritative status update.
          removeIdsFromSelection([entry.id]);
        })
        .catch((error) =>
          notifyToast({
            title: "Restore failed",
            description: error instanceof Error ? error.message : "Unable to restore document.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, removeIdsFromSelection, workspaceId],
  );

  // Bulk actions — avoid full invalidations; rely on SSE for authoritative updates.
  const bulkDeleteDocuments = useCallback(
    (documentIds?: string[]) => {
      const docs = (documentIds?.length
        ? documentIds
            .map((id) => documentsByEntryId.get(id))
            .filter((doc): doc is DocumentEntry => Boolean(doc?.record))
        : visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record)) as DocumentEntry[];

      if (docs.length === 0) return;

      const ids = docs.map((doc) => doc.id);

      void deleteWorkspaceDocumentsBatch(workspaceId, ids)
        .then(() => {
          notifyToast({ title: "Documents deleted", description: `${docs.length} removed`, intent: "success" });

          removeFromListCache(ids);
          ids.forEach((id) => queryClient.removeQueries({ queryKey: documentsKeys.document(workspaceId, id) }));
          removeIdsFromSelection(ids);
        })
        .catch((error) =>
          notifyToast({
            title: "Bulk delete failed",
            description: error instanceof Error ? error.message : "Unable to delete documents.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, removeFromListCache, removeIdsFromSelection, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkArchiveDocuments = useCallback(
    (documentIds?: string[]) => {
      const docs = (documentIds?.length
        ? documentIds
            .map((id) => documentsByEntryId.get(id))
            .filter((doc): doc is DocumentEntry => Boolean(doc?.record))
        : visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record)) as DocumentEntry[];

      const eligible = docs.filter((doc) => doc.status !== "archived");
      if (eligible.length === 0) return;

      void archiveWorkspaceDocumentsBatch(workspaceId, eligible.map((doc) => doc.id))
        .then(() => {
          notifyToast({
            title: "Documents archived",
            description: `${eligible.length} archived`,
            intent: "success",
          });
          removeIdsFromSelection(eligible.map((d) => d.id));
        })
        .catch((error) =>
          notifyToast({
            title: "Bulk archive failed",
            description: error instanceof Error ? error.message : "Unable to archive documents.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, removeIdsFromSelection, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkRestoreDocuments = useCallback(
    (documentIds?: string[]) => {
      const docs = (documentIds?.length
        ? documentIds
            .map((id) => documentsByEntryId.get(id))
            .filter((doc): doc is DocumentEntry => Boolean(doc?.record))
        : visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record)) as DocumentEntry[];

      const eligible = docs.filter((doc) => doc.status === "archived");
      if (eligible.length === 0) return;

      void restoreWorkspaceDocumentsBatch(workspaceId, eligible.map((doc) => doc.id))
        .then(() => {
          notifyToast({
            title: "Documents restored",
            description: `${eligible.length} restored`,
            intent: "success",
          });
          removeIdsFromSelection(eligible.map((d) => d.id));
        })
        .catch((error) =>
          notifyToast({
            title: "Bulk restore failed",
            description: error instanceof Error ? error.message : "Unable to restore documents.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, removeIdsFromSelection, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkUpdateTags = useCallback(
    (payload: { add: string[]; remove: string[] }) => {
      const add = payload.add.filter(Boolean);
      const remove = payload.remove.filter(Boolean);
      if (add.length === 0 && remove.length === 0) return;

      const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
      if (docs.length === 0) return;

      void patchDocumentTagsBatch(workspaceId, docs.map((doc) => doc.id), { add, remove })
        .then(() => {
          notifyToast({
            title: "Tags applied",
            description: `${add.length} added · ${remove.length} removed`,
            intent: "success",
          });
          // SSE will refresh rows; no full invalidation.
        })
        .catch((error) => {
          notifyToast({
            title: "Bulk tag failed",
            description: error instanceof Error ? error.message : "Unable to apply tags.",
            intent: "danger",
          });
        });
    },
    [notifyToast, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkDownloadOriginals = useCallback(() => {
    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;

    docs.forEach((d) => void downloadOriginalDocument(workspaceId, d.id, d.name).catch(() => undefined));
    notifyToast({ title: "Downloads started", description: `${docs.length} originals`, intent: "success" });
  }, [notifyToast, selectedIds, visibleDocuments, workspaceId]);

  const bulkDownloadOutputs = useCallback(() => {
    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;

    let triggered = 0;
    docs.forEach((d) => {
      const runId = getDocumentOutputRun(d.record)?.id ?? null;
      if (!runId) return;
      triggered += 1;
      void downloadRunOutputById(runId, d.name).catch(() => undefined);
    });

    if (triggered > 0) {
      notifyToast({ title: "Downloads started", description: `${triggered} outputs`, intent: "success" });
    } else {
      notifyToast({
        title: "No outputs ready",
        description: "Select documents with successful runs to download outputs.",
        intent: "warning",
      });
    }
  }, [notifyToast, selectedIds, visibleDocuments]);

  return {
    state: {
      viewMode,
      groupBy,
      search,
      selectedIds,
      activeId,
      previewOpen,
      activeSheetId,
      filters,
      activeViewId,
      saveViewOpen,
      selectedRunId,
      listSettings,
    },
    derived: {
      now,
      documents,
      visibleDocuments,
      activeDocument,
      boardColumns,

      isLoading: documentsQuery.isLoading,
      isError: documentsQuery.isError,
      hasNextPage: Boolean(documentsQuery.hasNextPage),
      isFetchingNextPage: documentsQuery.isFetchingNextPage,

      people,
      currentUserKey,

      runs,
      runsLoading: runsQuery.isLoading,
      selectedRunId,
      activeRun,
      runLoading: runsQuery.isFetching,
      runMetrics: runMetricsQuery.data ?? null,
      runMetricsLoading: runMetricsQuery.isLoading,
      runMetricsError: runMetricsQuery.isError,

      outputUrl,
      workbook: workbookQuery.data ?? null,
      workbookLoading: workbookQuery.isLoading,
      workbookError: workbookQuery.isError,

      showNoDocuments,
      showNoResults,
      allVisibleSelected,
      someVisibleSelected,

      savedViews,
      activeComments,

      counts,

      lastUpdatedAt,
      isRefreshing,

      changesCursor,
      configMissing,
      processingPaused,

      uploads: {
        items: uploadManager.items,
        summary: uploadManager.summary,
      },
    },
    refs: {
      fileInputRef,
    },
    actions: {
      setSearch: setSearchValue,
      setViewMode: setViewModeValue,
      setGroupBy: setGroupByValue,

      updateSelection,
      selectAllVisible,
      clearSelection,

      openPreview,
      closePreview,

      setActiveSheetId: setActiveSheetIdValue,

      queueUploads,
      handleUploadClick,
      pauseUpload,
      resumeUpload,
      retryUpload,
      cancelUpload,
      removeUpload,
      clearCompletedUploads,

      refreshDocuments,
      loadMore,

      handleKeyNavigate,

      setFilters: setFiltersValue,
      setListSettings: setListSettingsValue,
      setBuiltInView,
      selectSavedView,
      openSaveView,
      closeSaveView,
      saveView,
      deleteView,

      updateTagsOptimistic,
      assignDocument,
      pickUpDocument,

      addComment,
      editComment,
      deleteComment,

      selectRun,

      downloadOutput,
      downloadOutputFromRow,
      downloadOriginal,
      reprocess,
      copyLink,

      deleteDocument,
      archiveDocument,
      restoreDocument,

      bulkDeleteDocuments,
      bulkArchiveDocuments,
      bulkRestoreDocuments,
      bulkUpdateTags,
      bulkDownloadOriginals,
      bulkDownloadOutputs,
    },
  };
}

function filterUploadEntries(entries: DocumentEntry[], filters: DocumentsFilters, search: string): DocumentEntry[] {
  const searchValue = search.trim().toLowerCase();
  const hasSearch = searchValue.length >= 2;
  const statusFilters = filters.statuses;

  return entries.filter((doc) => {
    if (hasSearch) {
      const haystack = [
        doc.name,
        doc.uploaderLabel ?? "",
        doc.tags.join(" "),
        doc.assigneeLabel ?? "",
        doc.assigneeKey ?? "",
        doc.fileType,
      ]
        .join(" ")
        .toLowerCase();

      if (!haystack.includes(searchValue)) return false;
    }

    if (statusFilters.length > 0 && !statusFilters.includes(doc.status)) return false;
    if (filters.fileTypes.length > 0 && !filters.fileTypes.includes(doc.fileType)) return false;

    if (filters.tags.length > 0) {
      if (filters.tagMode === "all") {
        if (!filters.tags.every((t) => doc.tags.includes(t))) return false;
      } else if (!filters.tags.some((t) => doc.tags.includes(t))) {
        return false;
      }
    }

    if (filters.assignees.length > 0) {
      const includeUnassigned = filters.assignees.includes(UNASSIGNED_KEY);
      const assignedMatch = doc.assigneeKey ? filters.assignees.includes(doc.assigneeKey) : false;
      const unassignedMatch = !doc.assigneeKey && includeUnassigned;
      if (!assignedMatch && !unassignedMatch) return false;
    }

    return true;
  });
}

/**
 * Compact a batch by keeping only the latest change per document id.
 * This prevents 1000 upserts for the same document from causing 1000 merges.
 */
function compactDocumentChanges(changes: DocumentChangeEntry[]): DocumentChangeEntry[] {
  if (changes.length <= 1) return changes;

  const seen = new Set<string>();
  const deduped: DocumentChangeEntry[] = [];

  for (let index = changes.length - 1; index >= 0; index -= 1) {
    const change = changes[index];
    const id = change.documentId ?? change.row?.id;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    deduped.push(change);
  }

  return deduped.reverse();
}

function statusLabel(status: DocumentStatus) {
  switch (status) {
    case "processed":
      return "Processed";
    case "processing":
      return "Processing";
    case "failed":
      return "Failed";
    case "archived":
      return "Archived";
    case "uploaded":
      return "Uploaded";
    default:
      return status;
  }
}
