import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MutableRefObject,
} from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";

import { ApiError } from "@shared/api";
import { useConfigurationsQuery } from "@shared/configurations";
import { useNotifications } from "@shared/notifications";
import { resolveApiUrl } from "@shared/api/client";
import { documentChangesStreamUrl, streamDocumentChanges, type DocumentUploadResponse } from "@shared/documents";
import {
  useUploadManager,
  type UploadManagerItem,
  type UploadManagerQueueItem,
  type UploadManagerStatus,
  type UploadManagerSummary,
} from "@shared/documents/uploadManager";
import { streamRunEvents } from "@shared/runs/api";

import type { RunResource } from "@schema";

import {
  DOCUMENTS_PAGE_SIZE,
  archiveWorkspaceDocument,
  archiveWorkspaceDocumentsBatch,
  buildDocumentEntry,
  createRunForDocument,
  deleteWorkspaceDocument,
  deleteWorkspaceDocumentsBatch,
  documentsKeys,
  downloadOriginalDocument,
  downloadRunOutput,
  downloadRunOutputById,
  fetchRunMetrics,
  fetchWorkbookPreview,
  fetchWorkspaceDocumentById,
  fetchWorkspaceDocuments,
  fetchWorkspaceMembers,
  fetchWorkspaceRunsForDocument,
  getDocumentOutputRun,
  patchWorkspaceDocument,
  patchWorkspaceDocumentTags,
  patchWorkspaceDocumentTagsBatch,
  restoreWorkspaceDocument,
  restoreWorkspaceDocumentsBatch,
  runHasDownloadableOutput,
  runOutputDownloadUrl,
} from "../data";
import { DEFAULT_LIST_SETTINGS, normalizeListSettings, resolveRefreshIntervalMs } from "../listSettings";
import { mergeDocumentChangeIntoPages } from "../changeFeed";
import type {
  BoardColumn,
  BoardGroup,
  DocumentComment,
  DocumentEntry,
  DocumentPageResult,
  DocumentChangeEntry,
  DocumentsFilters,
  DocumentStatus,
  ListSettings,
  ListDocumentsQuery,
  RunMetricsResource,
  SavedView,
  ViewMode,
  WorkbookPreview,
  WorkspacePerson,
} from "../types";
import { copyToClipboard, fileTypeFromName, formatBytes, parseTimestamp, shortId } from "../utils";
import {
  ACTIVE_DOCUMENT_STATUSES,
  type BuiltInViewId,
  DEFAULT_DOCUMENT_FILTERS,
  UNASSIGNED_KEY,
  buildFiltersForBuiltInView,
  normalizeAssignees,
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

  handleKeyNavigate: (event: KeyboardEvent<HTMLDivElement>) => void;

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

const STATUS_ORDER: DocumentStatus[] = ["queued", "processing", "ready", "failed", "archived"];

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

export function useDocumentsModel({
  workspaceId,
  currentUserLabel,
  currentUserId,
  processingPaused,
  initialFilters,
}: {
  workspaceId: string;
  currentUserLabel: string;
  currentUserId: string;
  processingPaused: boolean;
  initialFilters?: DocumentsFilters;
}): WorkbenchModel {
  const { notifyToast } = useNotifications();
  const queryClient = useQueryClient();

  const currentUserKey = `user:${currentUserId}`;
  const initialFiltersValue = initialFilters ?? DEFAULT_DOCUMENT_FILTERS;
  const initialSavedViews = useMemo(() => loadSavedViews(workspaceId), [workspaceId]);

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
  const [commentsByDocId, setCommentsByDocId] = useState<Record<string, DocumentComment[]>>(() => loadComments(workspaceId));
  const [changesCursor, setChangesCursor] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const selectionAnchorRef = useRef<string | null>(null);
  const shiftPressedRef = useRef(false);
  const uploadCreatedAtRef = useRef(new Map<string, number>());
  const handledUploadsRef = useRef(new Set<string>());
  const uploadIdMapRef = useRef(new Map<string, string>());
  const runStreamControllersRef = useRef(new Map<string, AbortController>());
  const runStreamWorkspaceRef = useRef(workspaceId);
  const changesCursorRef = useRef<string | null>(null);
  const changeStreamControllerRef = useRef<AbortController | null>(null);
  const pendingChangesRef = useRef<DocumentChangeEntry[]>([]);
  const flushTimerRef = useRef<number | null>(null);
  const lastChangeCursorRef = useRef<string | null>(null);
  const refreshTimerRef = useRef<number | null>(null);
  const refreshInFlightRef = useRef(false);
  const refreshQueuedRef = useRef(false);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

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

  useEffect(() => {
    setSavedViews(loadSavedViews(workspaceId));
    setCommentsByDocId(loadComments(workspaceId));
    setListSettings(loadListSettings(workspaceId));
    uploadIdMapRef.current.clear();
  }, [workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;
    storeListSettings(workspaceId, listSettings);
  }, [listSettings, workspaceId]);

  const uploadManager = useUploadManager({ workspaceId });

  const configurationsQuery = useConfigurationsQuery({ workspaceId });
  const { refetch: refetchConfigurations } = configurationsQuery;
  const activeConfiguration = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    return items.find((config) => config.status === "active") ?? null;
  }, [configurationsQuery.data?.items]);
  const configMissing = configurationsQuery.isSuccess && !activeConfiguration;

  const sort = "-created_at";
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
  const refreshInterval = useMemo(
    () => resolveRefreshIntervalMs(listSettings.refreshInterval),
    [listSettings.refreshInterval],
  );
  const changeDetectionEnabled = listSettings.refreshInterval === "auto";

  const documentsQuery = useInfiniteQuery<DocumentPageResult>({
    queryKey: listKey,
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort,
          page: typeof pageParam === "number" ? pageParam : 1,
          pageSize: listSettings.pageSize ?? DOCUMENTS_PAGE_SIZE,
          query: buildDocumentsQuery(filters, search),
        },
        signal,
      ),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    refetchInterval: refreshInterval,
  });
  const { refetch: refetchDocuments } = documentsQuery;

  const documentsRaw = useMemo(
    () => documentsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [documentsQuery.data?.pages],
  );

  useEffect(() => {
    const firstPage = documentsQuery.data?.pages[0];
    const cursor = firstPage?.changes_cursor ?? firstPage?.changesCursorHeader ?? null;
    if (!cursor) return;
    if (changesCursorRef.current === cursor) return;
    changesCursorRef.current = cursor;
    lastChangeCursorRef.current = cursor;
    setChangesCursor(cursor);
  }, [documentsQuery.data?.pages]);

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

  const documentsById = useMemo(() => new Map(documentsRaw.map((doc) => [doc.id, doc])), [documentsRaw]);
  const activeRunIds = useMemo(() => {
    const ids = new Set<string>();
    documentsRaw.forEach((doc) => {
      const lastRun = doc.last_run;
      if (!lastRun) return;
      if (lastRun.status === "queued" || lastRun.status === "running") {
        ids.add(lastRun.run_id);
      }
    });
    return Array.from(ids);
  }, [documentsRaw]);

  useEffect(() => {
    if (!workspaceId) return;

    const controllers = runStreamControllersRef.current;
    if (runStreamWorkspaceRef.current !== workspaceId) {
      controllers.forEach((controller) => controller.abort());
      controllers.clear();
      runStreamWorkspaceRef.current = workspaceId;
    }

    const nextIds = new Set(activeRunIds);
    controllers.forEach((controller, runId) => {
      if (!nextIds.has(runId)) {
        controller.abort();
        controllers.delete(runId);
      }
    });

    nextIds.forEach((runId) => {
      if (controllers.has(runId)) return;
      const controller = new AbortController();
      controllers.set(runId, controller);

      void (async () => {
        try {
          const eventsUrl = resolveApiUrl(`/api/v1/runs/${runId}/events/stream`);
          for await (const event of streamRunEvents(eventsUrl, controller.signal)) {
            if (event.event === "run.start" || event.event === "run.complete") {
              queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
            }
            if (event.event === "run.complete") break;
          }
        } catch (error) {
          if (!controller.signal.aborted) {
            console.warn("Run event stream failed", error);
          }
        } finally {
          controllers.delete(runId);
        }
      })();
    });
  }, [activeRunIds, queryClient, workspaceId]);

  useEffect(
    () => () => {
      runStreamControllersRef.current.forEach((controller) => controller.abort());
      runStreamControllersRef.current.clear();
    },
    [],
  );

  useEffect(
    () => () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    },
    [],
  );

  useEffect(() => {
    if (changeDetectionEnabled) return;
    changeStreamControllerRef.current?.abort();
    pendingChangesRef.current = [];
    lastChangeCursorRef.current = null;
    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  }, [changeDetectionEnabled]);

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
        pageSize: listSettings.pageSize ?? DOCUMENTS_PAGE_SIZE,
        query: buildDocumentsQuery(filters, search),
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
  }, [filters, listKey, listSettings.pageSize, queryClient, search, sort, workspaceId]);

  const scheduleDocumentsRefresh = useCallback(() => {
    if (refreshTimerRef.current) return;
    refreshTimerRef.current = window.setTimeout(() => {
      refreshTimerRef.current = null;
      void refreshDocumentsFirstPage();
    }, 500);
  }, [refreshDocumentsFirstPage]);

  const flushPendingChanges = useCallback(() => {
    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
    }
    flushTimerRef.current = null;
    const batch = pendingChangesRef.current.splice(0);
    if (batch.length === 0) return;

    let shouldRefresh = false;
    queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
      if (!existing) return existing;
      let data = existing;
      batch.forEach((change) => {
        const result = mergeDocumentChangeIntoPages(data, change, {
          filters,
          search,
          sort,
        });
        data = result.data;
        if (result.updatesAvailable) {
          shouldRefresh = true;
        }
      });
      return data;
    });

    batch.forEach((change) => {
      if (change.type === "document.upsert" && change.document) {
        queryClient.setQueryData(documentsKeys.document(workspaceId, change.document.id), change.document);
      }
      if (change.type === "document.deleted" && change.document_id) {
        queryClient.removeQueries({ queryKey: documentsKeys.document(workspaceId, change.document_id) });
      }
    });

    if (shouldRefresh) {
      scheduleDocumentsRefresh();
    }
  }, [filters, listKey, queryClient, scheduleDocumentsRefresh, search, sort, workspaceId]);

  const enqueueChange = useCallback(
    (change: DocumentChangeEntry) => {
      pendingChangesRef.current.push(change);
      if (flushTimerRef.current) return;
      flushTimerRef.current = window.setTimeout(() => {
        flushPendingChanges();
      }, 200);
    },
    [flushPendingChanges],
  );

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
        const streamUrl = documentChangesStreamUrl(workspaceId, { cursor });

        try {
          for await (const change of streamDocumentChanges(streamUrl, controller.signal)) {
            lastChangeCursorRef.current = change.cursor;
            enqueueChange(change);
            retryAttempt = 0;
          }
        } catch (error) {
          if (controller.signal.aborted) return;
          if (error instanceof ApiError && error.status === 410) {
            void refetchDocuments();
            return;
          }
          console.warn("Document change stream failed", error);
        }

        if (controller.signal.aborted) return;
        const baseDelay = 1000;
        const maxDelay = 30000;
        const delay = Math.min(maxDelay, baseDelay * 2 ** Math.min(retryAttempt, 5));
        retryAttempt += 1;
        const jitter = Math.floor(delay * 0.15 * Math.random());
        await sleep(delay + jitter);
      }
    })();

    return () => controller.abort();
  }, [changeDetectionEnabled, changesCursor, enqueueChange, refetchDocuments, workspaceId]);

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

  useEffect(() => {
    if (!configMissing) return;
    const interval = window.setInterval(() => {
      void refetchConfigurations();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [configMissing, refetchConfigurations]);

  useEffect(() => {
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
      return mapped ?? prev;
    });

    const anchor = selectionAnchorRef.current;
    if (anchor && uploadIdMapRef.current.has(anchor)) {
      selectionAnchorRef.current = uploadIdMapRef.current.get(anchor) ?? anchor;
    }
  }, [uploadManager.items]);

  const uploadEntries = useMemo(() => {
    const entries: DocumentEntry[] = [];
    uploadManager.items.forEach((item) => {
      const createdAt = uploadCreatedAtRef.current.get(item.id) ?? Date.now();
      const fileName = item.file.name;
      if (item.status === "succeeded" && item.response) {
        if (documentsById.has(item.response.id)) return;
        entries.push(buildDocumentEntry(item.response));
        return;
      }

      const status: DocumentStatus =
        item.status === "failed" ? "failed" : item.status === "uploading" ? "processing" : "queued";

      entries.push({
        id: item.id,
        name: fileName,
        status,
        fileType: fileTypeFromName(fileName),
        uploader: currentUserLabel,
        tags: [],
        createdAt,
        updatedAt: createdAt,
        size: formatBytes(item.file.size),
        stage: buildUploadStageLabel(item.status),
        progress: item.status === "uploading" ? item.progress.percent : undefined,
        error:
          item.status === "failed"
            ? {
                summary: item.error ?? "Upload failed",
                detail: "We could not upload this file. Check the connection and retry.",
                nextStep: "Retry now or remove the upload.",
              }
            : undefined,
        mapping: { attention: 0, unmapped: 0, pending: true },

        assigneeKey: null,
        assigneeLabel: null,
        commentCount: (commentsByDocId[item.id] ?? []).length,

        record: item.response,
        upload: item,
      });
    });
    return entries;
  }, [commentsByDocId, currentUserLabel, documentsById, uploadManager.items]);

  const apiEntriesBase = useMemo(() => documentsRaw.map((doc) => buildDocumentEntry(doc)), [documentsRaw]);

  const membersQuery = useQuery({
    queryKey: documentsKeys.members(workspaceId),
    queryFn: ({ signal }) => fetchWorkspaceMembers(workspaceId, signal),
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

  const activeDocQuery = useQuery({
    queryKey:
      activeId && workspaceId
        ? documentsKeys.document(workspaceId, activeId)
        : [...documentsKeys.root(), "document", "none"],
    queryFn: ({ signal }) => (activeId ? fetchWorkspaceDocumentById(workspaceId, activeId, signal) : Promise.reject()),
    enabled: Boolean(activeId && workspaceId) && !documentsById.has(activeId ?? ""),
    staleTime: 30_000,
  });

  const pinnedActiveEntry = useMemo(() => {
    if (!activeDocQuery.data) return null;
    return buildDocumentEntry(activeDocQuery.data);
  }, [activeDocQuery.data]);

  const baseDocuments = useMemo(() => {
    const all = [...filterUploadEntries(uploadEntries, filters, search), ...apiEntriesBase];
    if (pinnedActiveEntry && !all.some((d) => d.id === pinnedActiveEntry.id)) {
      return [pinnedActiveEntry, ...all];
    }
    return all;
  }, [apiEntriesBase, filters, pinnedActiveEntry, search, uploadEntries]);

  const documents = useMemo<DocumentEntry[]>(() => {
    return baseDocuments.map((doc) => {
      const assigneeKey = doc.assigneeKey ?? null;
      const commentCount = (commentsByDocId[doc.id] ?? []).length;

      return {
        ...doc,
        assigneeKey,
        assigneeLabel: assigneeLabelForKey(assigneeKey),
        commentCount,
      };
    });
  }, [assigneeLabelForKey, baseDocuments, commentsByDocId]);

  const documentsByEntryId = useMemo(() => new Map(documents.map((d) => [d.id, d])), [documents]);

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

  const visibleDocuments = useMemo(() => documents, [documents]);

  const boardColumns = useMemo<BoardColumn[]>(() => {
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
      if (doc.uploader) uploaderSet.add(doc.uploader);
    });
    const uploaders = Array.from(uploaderSet).sort((a, b) => a.localeCompare(b));
    const columns = uploaders.map((uploader) => ({
      id: uploader,
      label: uploader,
      items: visibleDocuments.filter((doc) => doc.uploader === uploader),
    }));
    columns.push({
      id: "__unassigned_uploader__",
      label: "Unassigned",
      items: visibleDocuments.filter((doc) => !doc.uploader),
    });
    return columns;
  }, [groupBy, visibleDocuments]);

  const selectableIds = useMemo(() => visibleDocuments.filter((doc) => doc.record).map((doc) => doc.id), [visibleDocuments]);
  const selectedDocumentIds = useMemo(() => {
    return documents
      .filter((doc) => selectedIds.has(doc.id) && doc.record)
      .map((doc) => doc.record!.id);
  }, [documents, selectedIds]);
  const visibleSelectedCount = useMemo(
    () => selectableIds.filter((id) => selectedIds.has(id)).length,
    [selectableIds, selectedIds],
  );
  const allVisibleSelected = selectableIds.length > 0 && visibleSelectedCount === selectableIds.length;
  const someVisibleSelected = visibleSelectedCount > 0 && !allVisibleSelected;

  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      selectableIds.forEach((id) => {
        if (previous.has(id)) next.add(id);
      });
      if (next.size === previous.size) return previous;
      return next;
    });
    if (selectionAnchorRef.current && !selectableIds.includes(selectionAnchorRef.current)) {
      selectionAnchorRef.current = null;
    }
  }, [selectableIds]);

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

  const counts = useMemo(() => {
    const assignedToMe = documents.filter((d) => d.assigneeKey === currentUserKey).length;
    const unassigned = documents.filter((d) => !d.assigneeKey).length;
    const assignedToMeOrUnassigned = documents.filter(
      (d) => d.assigneeKey === currentUserKey || !d.assigneeKey,
    ).length;
    const active = documents.filter((d) => ACTIVE_DOCUMENT_STATUSES.includes(d.status)).length;
    const processed = documents.filter((d) => d.status === "ready").length;
    const processing = documents.filter((d) => d.status === "processing" || d.status === "queued").length;
    const failed = documents.filter((d) => d.status === "failed").length;
    const archived = documents.filter((d) => d.status === "archived").length;
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

  const activeDocumentIdForRuns = activeDocument?.record?.id ?? null;

  const runsQuery = useQuery({
    queryKey: activeDocumentIdForRuns
      ? documentsKeys.runsForDocument(workspaceId, activeDocumentIdForRuns)
      : [...documentsKeys.workspace(workspaceId), "runs", "none"],
    queryFn: ({ signal }) =>
      activeDocumentIdForRuns
        ? fetchWorkspaceRunsForDocument(workspaceId, activeDocumentIdForRuns, signal)
        : Promise.resolve([]),
    enabled: Boolean(activeDocumentIdForRuns) && previewOpen,
    staleTime: 5_000,
    refetchInterval: previewOpen ? 7_500 : false,
  });

  const runs = useMemo(() => {
    const items = runsQuery.data ?? [];
    return items.slice().sort((a, b) => parseTimestamp(b.created_at) - parseTimestamp(a.created_at));
  }, [runsQuery.data]);

  const preferredRunId = activeDocument?.record?.last_run?.run_id ?? null;

  useEffect(() => {
    if (!previewOpen) return;
    setSelectedRunId((prev) => {
      const existing = prev && runs.some((r) => r.id === prev) ? prev : null;
      if (existing) return existing;

      if (preferredRunId && runs.some((r) => r.id === preferredRunId)) return preferredRunId;

      return runs[0]?.id ?? null;
    });
  }, [activeDocument?.id, preferredRunId, previewOpen, runs]);

  const activeRun = useMemo(() => {
    if (!selectedRunId) return null;
    return runs.find((r) => r.id === selectedRunId) ?? null;
  }, [runs, selectedRunId]);

  const shouldPollRunMetrics =
    previewOpen && activeRun ? activeRun.status === "running" || activeRun.status === "queued" : false;

  const runMetricsQuery = useQuery({
    queryKey: selectedRunId
      ? documentsKeys.runMetrics(selectedRunId)
      : [...documentsKeys.root(), "runMetrics", "none"],
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
    queryFn: ({ signal }) => (outputUrl ? fetchWorkbookPreview(outputUrl, signal) : Promise.reject(new Error("No output URL"))),
    enabled: Boolean(outputUrl) && previewOpen,
    staleTime: 30_000,
  });

  useEffect(() => {
    setActiveSheetId(null);
  }, [activeDocument?.id, selectedRunId]);

  useEffect(() => {
    if (workbookQuery.data?.sheets.length) setActiveSheetId(workbookQuery.data.sheets[0].name);
  }, [workbookQuery.data?.sheets]);

  const resolveViewId = useCallback(
    (nextFilters: DocumentsFilters, nextSearch: string) =>
      resolveActiveViewId(nextFilters, nextSearch, savedViews, currentUserKey),
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

  const updateSelection = useCallback(
    (id: string, options?: { mode?: "toggle" | "range"; checked?: boolean }) => {
      const isRange = options?.mode === "range" || shiftPressedRef.current;
      setSelectedIds((previous) => {
        const next = new Set(previous);
        const shouldSelect = isRange ? options?.checked ?? true : options?.checked ?? !previous.has(id);
        const anchorId = selectionAnchorRef.current;
        if (isRange && anchorId) {
          const startIndex = selectableIds.indexOf(anchorId);
          const endIndex = selectableIds.indexOf(id);
          if (startIndex !== -1 && endIndex !== -1) {
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
      if (!isRange || !selectionAnchorRef.current) {
        selectionAnchorRef.current = id;
      }
    },
    [selectableIds],
  );

  const selectAllVisible = useCallback(() => setSelectedIds(new Set(selectableIds)), [selectableIds]);
  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
    selectionAnchorRef.current = null;
  }, []);

  const openPreview = useCallback((id: string) => {
    selectionAnchorRef.current = id;
    setActiveId(id);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => setPreviewOpen(false), []);

  const setActiveSheetIdValue = useCallback((id: string) => setActiveSheetId(id), []);

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

  const refreshDocuments = useCallback(() => {
    void documentsQuery.refetch();
  }, [documentsQuery]);
  const loadMore = useCallback(() => {
    if (documentsQuery.hasNextPage) void documentsQuery.fetchNextPage();
  }, [documentsQuery]);

  const handleKeyNavigate = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, button, a, [role='button'], [role='menuitem']")) {
        return;
      }
      if (visibleDocuments.length === 0) return;
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

      event.preventDefault();
      const currentIndex = visibleDocuments.findIndex((doc) => doc.id === activeId);
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
    [activeId, visibleDocuments],
  );

  const setFiltersValue = useCallback(
    (next: DocumentsFilters) => {
      setFilters(next);
      setActiveViewId(resolveViewId(next, search));
    },
    [resolveViewId, search],
  );

  const setListSettingsValue = useCallback(
    (next: ListSettings) => {
      const normalized = normalizeListSettings(next);
      setListSettings(normalized);
    },
    [normalizeListSettings],
  );

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
      if (activeViewId === viewId) {
        setActiveViewId("all_documents");
      }
      notifyToast({ title: "View deleted", description: viewId, intent: "success" });
    },
    [activeViewId, notifyToast, savedViews, workspaceId],
  );

  const updateTagsOptimistic = useCallback(
    (documentId: string, nextTags: string[]) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;

      const prevTags = entry.tags;
      const add = nextTags.filter((tag) => !prevTags.includes(tag));
      const remove = prevTags.filter((tag) => !nextTags.includes(tag));
      if (add.length === 0 && remove.length === 0) return;

      void patchWorkspaceDocumentTags(workspaceId, entry.record.id, { add, remove })
        .then((updated) => {
          queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
            if (!existing?.pages) return existing;
            return {
              ...existing,
              pages: existing.pages.map((page) => ({
                ...page,
                items: (page.items ?? []).map((item) => (item.id === updated.id ? updated : item)),
              })),
            };
          });
          queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, updated.id) });
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

  const assignDocument = useCallback(
    (documentId: string, assigneeKey: string | null) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;
      const assigneeUserId = assigneeKey?.startsWith("user:") ? assigneeKey.slice(5) : null;

      void patchWorkspaceDocument(workspaceId, entry.record.id, { assigneeUserId })
        .then((updated) => {
          queryClient.setQueryData(listKey, (existing: InfiniteData<DocumentPageResult> | undefined) => {
            if (!existing?.pages) return existing;
            return {
              ...existing,
              pages: existing.pages.map((page) => ({
                ...page,
                items: (page.items ?? []).map((item) => (item.id === updated.id ? updated : item)),
              })),
            };
          });
          queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, updated.id) });
          notifyToast({
            title: "Assignment updated",
            description: assigneeKey ? (peopleByKey.get(assigneeKey)?.label ?? assigneeKey) : "Unassigned",
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
    [documentsByEntryId, listKey, notifyToast, peopleByKey, queryClient, workspaceId],
  );

  const pickUpDocument = useCallback(
    (documentId: string) => assignDocument(documentId, currentUserKey),
    [assignDocument, currentUserKey],
  );

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
        const nextList = list.map((c) =>
          c.id === commentId ? { ...c, body, mentions, updatedAt: Date.now() } : c,
        );
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

  const selectRun = useCallback((runId: string) => setSelectedRunId(runId), []);

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
      const runId = getDocumentOutputRun(doc.record)?.run_id ?? null;
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
      void downloadOriginalDocument(workspaceId, doc.record.id, doc.name)
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

      void createRunForDocument(activeRun.configuration_id, doc.record.id)
        .then((created) => {
          notifyToast({ title: "Reprocess queued", description: `Run ${shortId(created.id)}`, intent: "success" });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
        })
        .catch((error) =>
          notifyToast({
            title: "Reprocess failed",
            description: error instanceof Error ? error.message : "Unable to reprocess.",
            intent: "danger",
          }),
        );
    },
    [activeRun?.configuration_id, notifyToast, processingPaused, queryClient, workspaceId],
  );

  const copyLink = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record) return;
      const url = new URL(window.location.href);
      url.searchParams.set("doc", doc.record.id);

      void copyToClipboard(url.toString())
        .then(() => notifyToast({ title: "Link copied", description: "Share it with your team.", intent: "success" }))
        .catch(() =>
          notifyToast({ title: "Copy failed", description: "Unable to copy link to clipboard.", intent: "danger" }),
        );
    },
    [notifyToast],
  );

  const deleteDocument = useCallback(
    (documentId: string) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;
      void deleteWorkspaceDocument(workspaceId, entry.record.id)
        .then(() => {
          notifyToast({ title: "Document deleted", description: entry.name, intent: "success" });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
          queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, entry.record.id) });
          setSelectedIds((prev) => {
            if (!prev.has(documentId)) return prev;
            const next = new Set(prev);
            next.delete(documentId);
            return next;
          });
        })
        .catch((error) =>
          notifyToast({
            title: "Delete failed",
            description: error instanceof Error ? error.message : "Unable to delete document.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, workspaceId],
  );

  const archiveDocument = useCallback(
    (documentId: string) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;
      void archiveWorkspaceDocument(workspaceId, entry.record.id)
        .then(() => {
          notifyToast({ title: "Document archived", description: entry.name, intent: "success" });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
          queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, entry.record!.id) });
          setSelectedIds((prev) => {
            if (!prev.has(documentId)) return prev;
            const next = new Set(prev);
            next.delete(documentId);
            return next;
          });
        })
        .catch((error) =>
          notifyToast({
            title: "Archive failed",
            description: error instanceof Error ? error.message : "Unable to archive document.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, workspaceId],
  );

  const restoreDocument = useCallback(
    (documentId: string) => {
      const entry = documentsByEntryId.get(documentId);
      if (!entry?.record) return;
      void restoreWorkspaceDocument(workspaceId, entry.record.id)
        .then(() => {
          notifyToast({ title: "Document restored", description: entry.name, intent: "success" });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
          queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, entry.record!.id) });
          setSelectedIds((prev) => {
            if (!prev.has(documentId)) return prev;
            const next = new Set(prev);
            next.delete(documentId);
            return next;
          });
        })
        .catch((error) =>
          notifyToast({
            title: "Restore failed",
            description: error instanceof Error ? error.message : "Unable to restore document.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, workspaceId],
  );

  const bulkDeleteDocuments = useCallback(
    (documentIds?: string[]) => {
      const docs = (documentIds?.length
        ? documentIds.map((id) => documentsByEntryId.get(id)).filter((doc): doc is DocumentEntry => Boolean(doc?.record))
        : visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record)) as DocumentEntry[];

      if (docs.length === 0) return;
      void deleteWorkspaceDocumentsBatch(
        workspaceId,
        docs.map((doc) => doc.record!.id),
      )
        .then(() => {
          notifyToast({
            title: "Documents deleted",
            description: `${docs.length} removed`,
            intent: "success",
          });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
          docs.forEach((doc) => {
            queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, doc.record!.id) });
          });
          setSelectedIds((prev) => {
            const next = new Set(prev);
            docs.forEach((doc) => next.delete(doc.id));
            return next;
          });
        })
        .catch((error) =>
          notifyToast({
            title: "Bulk delete failed",
            description: error instanceof Error ? error.message : "Unable to delete documents.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkArchiveDocuments = useCallback(
    (documentIds?: string[]) => {
      const docs = (documentIds?.length
        ? documentIds.map((id) => documentsByEntryId.get(id)).filter((doc): doc is DocumentEntry => Boolean(doc?.record))
        : visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record)) as DocumentEntry[];

      const eligible = docs.filter((doc) => doc.status !== "archived");
      if (eligible.length === 0) return;

      void archiveWorkspaceDocumentsBatch(
        workspaceId,
        eligible.map((doc) => doc.record!.id),
      )
        .then(() => {
          notifyToast({
            title: "Documents archived",
            description: `${eligible.length} archived`,
            intent: "success",
          });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
          eligible.forEach((doc) => {
            queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, doc.record!.id) });
          });
          setSelectedIds((prev) => {
            const next = new Set(prev);
            eligible.forEach((doc) => next.delete(doc.id));
            return next;
          });
        })
        .catch((error) =>
          notifyToast({
            title: "Bulk archive failed",
            description: error instanceof Error ? error.message : "Unable to archive documents.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkRestoreDocuments = useCallback(
    (documentIds?: string[]) => {
      const docs = (documentIds?.length
        ? documentIds.map((id) => documentsByEntryId.get(id)).filter((doc): doc is DocumentEntry => Boolean(doc?.record))
        : visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record)) as DocumentEntry[];

      const eligible = docs.filter((doc) => doc.status === "archived");
      if (eligible.length === 0) return;

      void restoreWorkspaceDocumentsBatch(
        workspaceId,
        eligible.map((doc) => doc.record!.id),
      )
        .then(() => {
          notifyToast({
            title: "Documents restored",
            description: `${eligible.length} restored`,
            intent: "success",
          });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
          eligible.forEach((doc) => {
            queryClient.invalidateQueries({ queryKey: documentsKeys.document(workspaceId, doc.record!.id) });
          });
          setSelectedIds((prev) => {
            const next = new Set(prev);
            eligible.forEach((doc) => next.delete(doc.id));
            return next;
          });
        })
        .catch((error) =>
          notifyToast({
            title: "Bulk restore failed",
            description: error instanceof Error ? error.message : "Unable to restore documents.",
            intent: "danger",
          }),
        );
    },
    [documentsByEntryId, notifyToast, queryClient, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkUpdateTags = useCallback(
    (payload: { add: string[]; remove: string[] }) => {
      const add = payload.add.filter(Boolean);
      const remove = payload.remove.filter(Boolean);
      if (add.length === 0 && remove.length === 0) return;

      const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
      if (docs.length === 0) return;

      void patchWorkspaceDocumentTagsBatch(
        workspaceId,
        docs.map((doc) => doc.record!.id),
        { add, remove },
      )
        .then(() => {
          notifyToast({
            title: "Tags applied",
            description: `${add.length} added · ${remove.length} removed`,
            intent: "success",
          });
          queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
        })
        .catch((error) => {
          notifyToast({
            title: "Bulk tag failed",
            description: error instanceof Error ? error.message : "Unable to apply tags.",
            intent: "danger",
          });
        });
    },
    [notifyToast, queryClient, selectedIds, visibleDocuments, workspaceId],
  );

  const bulkDownloadOriginals = useCallback(() => {
    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;
    docs.forEach((d) => {
      void downloadOriginalDocument(workspaceId, d.record!.id, d.name).catch(() => undefined);
    });
    notifyToast({ title: "Downloads started", description: `${docs.length} originals`, intent: "success" });
  }, [notifyToast, selectedIds, visibleDocuments, workspaceId]);

  const bulkDownloadOutputs = useCallback(() => {
    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;
    let triggered = 0;
    docs.forEach((d) => {
      const runId = getDocumentOutputRun(d.record)?.run_id ?? null;
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

function buildDocumentsQuery(filters: DocumentsFilters, search: string): Partial<ListDocumentsQuery> {
  const query: Partial<ListDocumentsQuery> = {};
  const trimmedSearch = search.trim();
  if (trimmedSearch.length >= 2) {
    query.q = trimmedSearch;
  }
  if (filters.statuses.length > 0) {
    query.display_status = filters.statuses;
  }
  if (filters.fileTypes.length > 0) {
    const fileTypes = filters.fileTypes.filter((type) => type !== "unknown");
    if (fileTypes.length > 0) query.file_type = fileTypes;
  }
  if (filters.tags.length > 0) {
    query.tags = filters.tags;
    query.tag_mode = filters.tagMode;
  }
  if (filters.assignees.length > 0) {
    const { assigneeIds, includeUnassigned } = normalizeAssignees(filters.assignees);
    if (assigneeIds.length > 0) {
      query.assignee_user_id = assigneeIds;
    }
    if (includeUnassigned) {
      query.assignee_unassigned = true;
    }
  }
  return query;
}

function filterUploadEntries(entries: DocumentEntry[], filters: DocumentsFilters, search: string): DocumentEntry[] {
  const searchValue = search.trim().toLowerCase();
  const hasSearch = searchValue.length >= 2;
  const statusFilters = filters.statuses;

  return entries.filter((doc) => {
    if (hasSearch) {
      const haystack = [
        doc.name,
        doc.uploader ?? "",
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

function buildUploadStageLabel(status: UploadManagerStatus) {
  switch (status) {
    case "paused":
      return "Upload paused";
    case "cancelled":
      return "Upload cancelled";
    case "failed":
      return "Upload failed";
    case "uploading":
      return "Uploading";
    case "queued":
      return "Queued for upload";
    case "succeeded":
      return "Upload complete";
    default:
      return "Queued for upload";
  }
}

function statusLabel(status: DocumentStatus) {
  switch (status) {
    case "ready":
      return "Processed";
    case "processing":
      return "Processing";
    case "failed":
      return "Failed";
    case "archived":
      return "Archived";
    case "queued":
      return "Queued";
    default:
      return status;
  }
}
