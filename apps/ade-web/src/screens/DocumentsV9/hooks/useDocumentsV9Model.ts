import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type MutableRefObject,
} from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@shared/api";
import { useNotifications } from "@shared/notifications";
import { uploadWorkspaceDocument, type DocumentUploadResponse } from "@shared/documents";
import { useUploadQueue } from "@shared/uploads/queue";

import {
  DOCUMENTS_PAGE_SIZE,
  buildDocumentEntry,
  buildUploadEntry,
  createRunForDocument,
  documentsV9Keys,
  downloadRunOutput,
  downloadWorkspaceDocumentOriginal,
  fetchWorkbookPreview,
  fetchWorkspaceDocuments,
  fetchWorkspaceRunsForDocument,
  getDocumentOutputRun,
  patchWorkspaceDocumentTags,
  patchWorkspaceDocumentTagsBatch,
  runHasDownloadableOutput,
  runOutputDownloadUrl,
} from "../data";

import type {
  BoardColumn,
  BoardGroup,
  DocumentEntry,
  DocumentsFilters,
  DocumentsSavedView,
  DocumentStatus,
  RunResource,
  ViewMode,
  WorkbookPreview,
} from "../types";
import { parseTimestamp, stableId } from "../utils";

type WorkbenchState = {
  viewMode: ViewMode;
  groupBy: BoardGroup;
  hideEmptyColumns: boolean;
  sort: string | null;
  search: string;
  filters: DocumentsFilters;

  activeViewKey: string; // builtin:* or saved:*
  savedViews: DocumentsSavedView[];

  selectedIds: Set<string>;
  activeId: string | null;
  previewOpen: boolean;

  activeRunId: string | null;
  activeSheetId: string | null;
};

type WorkbenchDerived = {
  now: number;
  documents: DocumentEntry[];
  visibleDocuments: DocumentEntry[];
  activeDocument: DocumentEntry | null;

  boardColumns: BoardColumn[];

  statusCounts: Record<DocumentStatus, number>;

  isLoading: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;

  // Runs
  runs: RunResource[];
  runsLoading: boolean;
  activeRun: RunResource | null;

  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;

  showNoDocuments: boolean;
  showNoResults: boolean;
  allVisibleSelected: boolean;

  activeViewLabel: string;
  showSaveView: boolean;
};

type WorkbenchRefs = {
  searchRef: MutableRefObject<HTMLInputElement | null>;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
};

type WorkbenchActions = {
  setSearch: (value: string) => void;
  setViewMode: (value: ViewMode) => void;
  setGroupBy: (value: BoardGroup) => void;
  setHideEmptyColumns: (value: boolean) => void;
  setSort: (value: string | null) => void;

  toggleStatusFilter: (status: DocumentStatus) => void;
  toggleFileTypeFilter: (type: DocumentsFilters["fileTypes"][number]) => void;
  setTagMode: (mode: DocumentsFilters["tagMode"]) => void;
  toggleTagFilter: (tag: string) => void;
  clearFilters: () => void;

  selectBuiltInView: (id: "all" | "ready" | "processing" | "failed") => void;
  selectSavedView: (id: string) => void;
  saveCurrentView: (name: string) => void;
  deleteSavedView: (id: string) => void;

  toggleSelect: (id: string) => void;
  selectAllVisible: () => void;
  clearSelection: () => void;

  openPreview: (id: string) => void;
  closePreview: () => void;

  setActiveRunId: (id: string) => void;
  setActiveSheetId: (id: string) => void;

  handleUploadClick: () => void;
  handleFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;

  downloadOriginal: (doc: DocumentEntry) => void;
  downloadOutputFromRow: (doc: DocumentEntry) => void;
  downloadOutputFromPreview: (doc: DocumentEntry, run: RunResource | null) => void;

  reprocessDocument: (doc: DocumentEntry) => void;

  toggleTagOnDocument: (doc: DocumentEntry, tag: string) => void;

  bulkAddTagPrompt: () => void;
  bulkDownloadOriginals: () => void;
  bulkReprocess: () => void;

  refreshDocuments: () => void;
  loadMore: () => void;

  handleKeyNavigate: (event: KeyboardEvent<HTMLDivElement>) => void;
};

export type WorkbenchModel = {
  state: WorkbenchState;
  derived: WorkbenchDerived;
  refs: WorkbenchRefs;
  actions: WorkbenchActions;
};

const STATUS_ORDER: DocumentStatus[] = ["queued", "processing", "ready", "failed", "archived"];

const STORAGE_KEY_PREFIX = "ade.documents.v9.views";

function loadSavedViews(workspaceId: string): DocumentsSavedView[] {
  if (typeof window === "undefined") return [];
  const key = `${STORAGE_KEY_PREFIX}.${workspaceId}`;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as DocumentsSavedView[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistSavedViews(workspaceId: string, views: DocumentsSavedView[]) {
  if (typeof window === "undefined") return;
  const key = `${STORAGE_KEY_PREFIX}.${workspaceId}`;
  window.localStorage.setItem(key, JSON.stringify(views));
}

function defaultFilters(): DocumentsFilters {
  return { statuses: [], fileTypes: [], tags: [], tagMode: "any" };
}

function resolveApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const detail = error.problem?.detail as unknown;
    if (typeof detail === "string" && detail.length > 0) {
      return detail;
    }
    if (detail && typeof detail === "object" && "error" in detail) {
      const message = (detail as { error?: { message?: string } }).error?.message;
      if (message) {
        return message;
      }
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function isActiveConfigurationMissing(error: unknown) {
  if (!(error instanceof ApiError)) {
    return false;
  }
  return error.problem?.detail === "active_configuration_not_found";
}

function isSameViewState(a: DocumentsSavedView["state"], b: DocumentsSavedView["state"]) {
  const normalize = (s: DocumentsSavedView["state"]) => ({
    ...s,
    filters: {
      ...s.filters,
      statuses: [...s.filters.statuses].slice().sort(),
      fileTypes: [...s.filters.fileTypes].slice().sort(),
      tags: [...s.filters.tags].slice().sort(),
    },
  });
  return JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
}

export function useDocumentsV9Model({
  workspaceId,
  currentUserLabel,
}: {
  workspaceId: string;
  currentUserLabel: string;
}): WorkbenchModel {
  const { notifyToast } = useNotifications();
  const queryClient = useQueryClient();

  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [groupBy, setGroupBy] = useState<BoardGroup>("status");
  const [hideEmptyColumns, setHideEmptyColumns] = useState(false);
  const [sort, setSort] = useState<string | null>("-created_at");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<DocumentsFilters>(() => defaultFilters());

  const [savedViews, setSavedViews] = useState<DocumentsSavedView[]>(() => loadSavedViews(workspaceId));
  const [activeViewKey, setActiveViewKey] = useState<string>("builtin:all");

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);

  const [now, setNow] = useState(() => Date.now());

  const searchRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadCreatedAtRef = useRef(new Map<string, number>());
  const handledUploadsRef = useRef(new Set<string>());

  useEffect(() => {
    setSavedViews(loadSavedViews(workspaceId));
  }, [workspaceId]);

  useEffect(() => {
    persistSavedViews(workspaceId, savedViews);
  }, [savedViews, workspaceId]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "/") {
        const target = event.target as HTMLElement | null;
        if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === "Escape") setPreviewOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const startUpload = useCallback(
    (file: File, handlers: { onProgress: (progress: { loaded: number; total: number | null; percent: number | null }) => void }) =>
      uploadWorkspaceDocument(workspaceId, file, { onProgress: handlers.onProgress }),
    [workspaceId],
  );

  const uploadQueue = useUploadQueue<DocumentUploadResponse>({ startUpload });

  const normalizedSearch = search.trim();
  const normalizedFilters = useMemo<DocumentsFilters>(
    () => ({
      statuses: [...filters.statuses].slice().sort(),
      fileTypes: [...filters.fileTypes].slice().sort(),
      tags: [...filters.tags].slice().sort(),
      tagMode: filters.tagMode,
    }),
    [filters],
  );

  const listKey = useMemo(
    () =>
      documentsV9Keys.list(workspaceId, {
        sort,
        search: normalizedSearch,
        filters: normalizedFilters,
      }),
    [normalizedFilters, normalizedSearch, sort, workspaceId],
  );

  const documentsQuery = useInfiniteQuery({
    queryKey: listKey,
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort,
          page: typeof pageParam === "number" ? pageParam : 1,
          pageSize: DOCUMENTS_PAGE_SIZE,
          search: normalizedSearch,
          filters: normalizedFilters,
        },
        signal,
      ),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: workspaceId.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });

  const documentsRaw = useMemo(
    () => documentsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [documentsQuery.data?.pages],
  );

  const documentsById = useMemo(() => new Map(documentsRaw.map((doc) => [doc.id, doc])), [documentsRaw]);

  useEffect(() => {
    uploadQueue.items.forEach((item) => {
      if (item.status === "succeeded" && item.response && !handledUploadsRef.current.has(item.id)) {
        handledUploadsRef.current.add(item.id);
        queryClient.invalidateQueries({ queryKey: documentsV9Keys.workspace(workspaceId) });
      }
      if (item.status === "failed" && item.error && !handledUploadsRef.current.has(`fail-${item.id}`)) {
        handledUploadsRef.current.add(`fail-${item.id}`);
        notifyToast({ title: "Upload failed", description: item.error, intent: "danger" });
      }
    });
  }, [notifyToast, queryClient, uploadQueue.items, workspaceId]);

  const uploadEntries = useMemo(() => {
    const entries: DocumentEntry[] = [];
    uploadQueue.items.forEach((item) => {
      const createdAt = uploadCreatedAtRef.current.get(item.id) ?? Date.now();
      if (item.status === "succeeded" && item.response) {
        if (documentsById.has(item.response.id)) return;
        entries.push(buildDocumentEntry(item.response, { upload: item }));
        return;
      }
      entries.push(buildUploadEntry(item, currentUserLabel, createdAt));
    });
    return entries;
  }, [currentUserLabel, documentsById, uploadQueue.items]);

  const normalizedSearchLower = normalizedSearch.toLowerCase();
  const filteredUploadEntries = useMemo(() => {
    if (uploadEntries.length === 0) return [];
    const hasSearch = normalizedSearchLower.length >= 2;
    return uploadEntries.filter((doc) => {
      if (hasSearch) {
        const haystack = [doc.name, doc.uploader ?? "", doc.tags.join(" ")].join(" ").toLowerCase();
        if (!haystack.includes(normalizedSearchLower)) return false;
      }

      if (filters.statuses.length > 0 && !filters.statuses.includes(doc.status)) {
        return false;
      }

      if (filters.fileTypes.length > 0 && !filters.fileTypes.includes(doc.fileType)) {
        return false;
      }

      if (filters.tags.length > 0) {
        if (filters.tagMode === "all") {
          return filters.tags.every((t) => doc.tags.includes(t));
        }
        return doc.tags.some((t) => filters.tags.includes(t));
      }

      return true;
    });
  }, [filters, normalizedSearchLower, uploadEntries]);

  const apiEntries = useMemo(() => documentsRaw.map((doc) => buildDocumentEntry(doc)), [documentsRaw]);
  const documents = useMemo(() => [...filteredUploadEntries, ...apiEntries], [filteredUploadEntries, apiEntries]);
  const documentsByEntryId = useMemo(() => new Map(documents.map((doc) => [doc.id, doc])), [documents]);

  // Keep selected ids valid
  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      previous.forEach((id) => {
        if (documentsByEntryId.has(id)) next.add(id);
      });
      return next;
    });
  }, [documentsByEntryId]);

  // Active doc handling
  useEffect(() => {
    if (documents.length === 0) {
      setActiveId(null);
      setPreviewOpen(false);
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

  // Status counts for sidebar
  const statusCounts = useMemo(() => {
    const counts: Record<DocumentStatus, number> = {
      queued: 0,
      processing: 0,
      ready: 0,
      failed: 0,
      archived: 0,
    };
    documents.forEach((d) => {
      counts[d.status] += 1;
    });
    return counts;
  }, [documents]);

  // Runs for active document (only when we have a real document record id).
  const activeDocumentIdForRuns = activeDocument?.record?.id ?? null;

  const runsQuery = useQuery({
    queryKey: activeDocumentIdForRuns
      ? documentsV9Keys.runsForDocument(workspaceId, activeDocumentIdForRuns)
      : [...documentsV9Keys.workspace(workspaceId), "runs", "none"],
    queryFn: ({ signal }) =>
      activeDocumentIdForRuns
        ? fetchWorkspaceRunsForDocument(workspaceId, activeDocumentIdForRuns, { page: 1, pageSize: 50 }, signal)
        : Promise.resolve({ items: [], page: 1, page_size: 50, has_next: false, has_previous: false }),
    enabled: Boolean(activeDocumentIdForRuns) && previewOpen,
    staleTime: 5_000,
    refetchInterval: previewOpen ? 7_500 : false,
  });

  const runs = useMemo(() => {
    const items = runsQuery.data?.items ?? [];
    return items
      .slice()
      .sort((a, b) => parseTimestamp(b.created_at) - parseTimestamp(a.created_at));
  }, [runsQuery.data?.items]);

  // Choose default active run when doc changes.
  useEffect(() => {
    if (!previewOpen) return;
    setActiveRunId((prev) => {
      const existing = prev && runs.some((r) => r.id === prev) ? prev : null;
      if (existing) return existing;

      const preferred = activeDocument?.record?.last_run?.run_id ?? null;
      if (preferred && runs.some((r) => r.id === preferred)) return preferred;

      return runs[0]?.id ?? null;
    });
  }, [activeDocument?.id, previewOpen, runs]);

  const activeRun = useMemo(() => {
    if (!activeRunId) return null;
    return runs.find((r) => r.id === activeRunId) ?? null;
  }, [activeRunId, runs]);

  const outputUrl = useMemo(() => {
    if (!activeRun) return null;
    if (!runHasDownloadableOutput(activeRun)) return null;
    return runOutputDownloadUrl(activeRun);
  }, [activeRun]);

  const workbookQuery = useQuery<WorkbookPreview>({
    queryKey: outputUrl ? documentsV9Keys.workbook(outputUrl) : [...documentsV9Keys.root(), "workbook", "none"],
    queryFn: ({ signal }) => (outputUrl ? fetchWorkbookPreview(outputUrl, signal) : Promise.reject(new Error("No output URL"))),
    enabled: Boolean(outputUrl) && previewOpen,
    staleTime: 30_000,
  });

  useEffect(() => {
    setActiveSheetId(null);
  }, [activeDocument?.id, activeRunId]);

  useEffect(() => {
    if (workbookQuery.data?.sheets.length) setActiveSheetId(workbookQuery.data.sheets[0].name);
  }, [workbookQuery.data?.sheets]);

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
      id: "__unassigned__",
      label: "Unassigned",
      items: visibleDocuments.filter((doc) => !doc.uploader),
    });
    return columns;
  }, [groupBy, visibleDocuments]);

  const selectableIds = useMemo(
    () => visibleDocuments.filter((doc) => doc.record).map((doc) => doc.id),
    [visibleDocuments],
  );
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));
  const hasActiveFilters =
    normalizedSearch.length >= 2 ||
    filters.statuses.length > 0 ||
    filters.fileTypes.length > 0 ||
    filters.tags.length > 0;
  const showNoDocuments = documents.length === 0 && !hasActiveFilters;
  const showNoResults = documents.length === 0 && hasActiveFilters;

  // Active view label + save view visibility
  const activeViewLabel = useMemo(() => {
    if (activeViewKey.startsWith("saved:")) {
      const id = activeViewKey.replace("saved:", "");
      const view = savedViews.find((v) => v.id === id);
      return view ? `Saved view · ${view.name}` : "Saved view";
    }
    if (activeViewKey === "builtin:ready") return "View · Ready";
    if (activeViewKey === "builtin:processing") return "View · Processing";
    if (activeViewKey === "builtin:failed") return "View · Failed";
    return "All documents";
  }, [activeViewKey, savedViews]);

  const showSaveView = useMemo(() => {
    const currentState: DocumentsSavedView["state"] = {
      search,
      sort,
      viewMode,
      groupBy,
      filters,
    };

    if (activeViewKey.startsWith("saved:")) {
      const id = activeViewKey.replace("saved:", "");
      const view = savedViews.find((v) => v.id === id);
      if (!view) return true;
      return !isSameViewState(view.state, currentState);
    }
    // From builtin views: allow saving anytime if anything is “non-default”.
    const nonDefault =
      search.trim().length > 0 ||
      (sort ?? "-created_at") !== "-created_at" ||
      viewMode !== "grid" ||
      groupBy !== "status" ||
      filters.statuses.length > 0 ||
      filters.fileTypes.length > 0 ||
      filters.tags.length > 0;
    return nonDefault;
  }, [activeViewKey, filters, groupBy, savedViews, search, sort, viewMode]);

  // Actions
  const setSearchValue = useCallback((value: string) => setSearch(value), []);
  const setViewModeValue = useCallback((value: ViewMode) => setViewMode(value), []);
  const setGroupByValue = useCallback((value: BoardGroup) => setGroupBy(value), []);
  const setHideEmptyColumnsValue = useCallback((value: boolean) => setHideEmptyColumns(value), []);
  const setSortValue = useCallback((value: string | null) => setSort(value), []);

  const toggleStatusFilter = useCallback((status: DocumentStatus) => {
    setFilters((prev) => {
      const exists = prev.statuses.includes(status);
      return { ...prev, statuses: exists ? prev.statuses.filter((s) => s !== status) : [...prev.statuses, status] };
    });
  }, []);

  const toggleFileTypeFilter = useCallback((type: DocumentsFilters["fileTypes"][number]) => {
    setFilters((prev) => {
      const exists = prev.fileTypes.includes(type);
      return { ...prev, fileTypes: exists ? prev.fileTypes.filter((t) => t !== type) : [...prev.fileTypes, type] };
    });
  }, []);

  const setTagMode = useCallback((mode: DocumentsFilters["tagMode"]) => {
    setFilters((prev) => ({ ...prev, tagMode: mode }));
  }, []);

  const toggleTagFilter = useCallback((tag: string) => {
    setFilters((prev) => {
      const exists = prev.tags.includes(tag);
      return { ...prev, tags: exists ? prev.tags.filter((t) => t !== tag) : [...prev.tags, tag] };
    });
  }, []);

  const clearFilters = useCallback(() => setFilters(defaultFilters()), []);

  const selectBuiltInView = useCallback((id: "all" | "ready" | "processing" | "failed") => {
    setActiveViewKey(`builtin:${id}`);
    // Convention: builtin views are shortcuts; we set status filters accordingly and keep other filters visible.
    setFilters((prev) => {
      if (id === "all") return { ...prev, statuses: [] };
      if (id === "ready") return { ...prev, statuses: ["ready"] };
      if (id === "failed") return { ...prev, statuses: ["failed"] };
      // processing = queued + processing
      return { ...prev, statuses: ["queued", "processing"] };
    });
  }, []);

  const selectSavedView = useCallback(
    (id: string) => {
      const view = savedViews.find((v) => v.id === id);
      if (!view) return;
      setActiveViewKey(`saved:${id}`);
      setSearch(view.state.search);
      setSort(view.state.sort);
      setViewMode(view.state.viewMode);
      setGroupBy(view.state.groupBy);
      setFilters(view.state.filters);
    },
    [savedViews],
  );

  const saveCurrentView = useCallback(
    (name: string) => {
      const state: DocumentsSavedView["state"] = { search, sort, viewMode, groupBy, filters };
      const nowTs = Date.now();

      setSavedViews((prev) => {
        // If currently on a saved view, update it; otherwise create new.
        if (activeViewKey.startsWith("saved:")) {
          const id = activeViewKey.replace("saved:", "");
          const next = prev.map((v) => (v.id === id ? { ...v, name, state, updatedAt: nowTs } : v));
          return next;
        }
        const nextView: DocumentsSavedView = {
          id: stableId(),
          name,
          createdAt: nowTs,
          updatedAt: nowTs,
          state,
        };
        setActiveViewKey(`saved:${nextView.id}`);
        return [nextView, ...prev];
      });

      notifyToast({ title: "View saved", description: name, intent: "success" });
    },
    [activeViewKey, filters, groupBy, notifyToast, search, sort, viewMode],
  );

  const deleteSavedView = useCallback(
    (id: string) => {
      setSavedViews((prev) => prev.filter((v) => v.id !== id));
      if (activeViewKey === `saved:${id}`) setActiveViewKey("builtin:all");
    },
    [activeViewKey],
  );

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllVisible = useCallback(() => {
    setSelectedIds(new Set(selectableIds));
  }, [selectableIds]);

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const openPreview = useCallback((id: string) => {
    setActiveId(id);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => setPreviewOpen(false), []);

  const setActiveRunIdValue = useCallback((id: string) => setActiveRunId(id), []);
  const setActiveSheetIdValue = useCallback((id: string) => setActiveSheetId(id), []);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const nextItems = uploadQueue.enqueue(Array.from(files));
      const nowTimestamp = Date.now();
      nextItems.forEach((item, index) => {
        uploadCreatedAtRef.current.set(item.id, nowTimestamp + index * 1000);
      });
      notifyToast({
        title: `${nextItems.length} file${nextItems.length === 1 ? "" : "s"} added`,
        description: "Processing will begin automatically.",
        intent: "success",
      });
    },
    [notifyToast, uploadQueue],
  );

  const handleUploadClick = useCallback(() => fileInputRef.current?.click(), []);
  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      handleFiles(event.target.files);
      event.target.value = "";
    },
    [handleFiles],
  );

  const downloadOriginal = useCallback(
    (doc: DocumentEntry) => {
      if (!doc.record) return;
      void downloadWorkspaceDocumentOriginal(workspaceId, doc.record.id, doc.name)
        .then((filename) => notifyToast({ title: "Download started", description: filename, intent: "success" }))
        .catch((error) =>
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download file.",
            intent: "danger",
          }),
        );
    },
    [notifyToast, workspaceId],
  );

  const downloadOutputFromRow = useCallback(
    (doc: DocumentEntry) => {
      const runId = getDocumentOutputRun(doc.record)?.run_id ?? null;
      if (!doc.record || !runId) {
        notifyToast({ title: "Output not ready", description: "Open the document to see run history.", intent: "warning" });
        return;
      }
      void downloadRunOutput(runId, doc.name)
        .then((filename) => notifyToast({ title: "Download started", description: filename, intent: "success" }))
        .catch((error) =>
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download output.",
            intent: "danger",
          }),
        );
    },
    [notifyToast],
  );

  const downloadOutputFromPreview = useCallback(
    (doc: DocumentEntry, run: RunResource | null) => {
      if (!doc.record) return;
      const runId = run?.status === "succeeded" ? run.id : getDocumentOutputRun(doc.record)?.run_id ?? null;
      if (!runId) {
        notifyToast({ title: "Output not ready", description: "Select a successful run to download output.", intent: "warning" });
        return;
      }
      void downloadRunOutput(runId, doc.name)
        .then((filename) => notifyToast({ title: "Download started", description: filename, intent: "success" }))
        .catch((error) =>
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download output.",
            intent: "danger",
          }),
        );
    },
    [notifyToast],
  );

  const reprocessDocument = useCallback(
    (doc: DocumentEntry) => {
      if (!doc.record) return;

      void createRunForDocument(workspaceId, doc.record.id)
        .then((run) => {
          notifyToast({
            title: "Reprocess started",
            description: `Run ${run.id.slice(0, 8)}… queued`,
            intent: "success",
          });
          queryClient.invalidateQueries({ queryKey: documentsV9Keys.workspace(workspaceId) });
          queryClient.invalidateQueries({ queryKey: documentsV9Keys.runsForDocument(workspaceId, doc.record!.id) });
        })
        .catch((error) => {
          if (isActiveConfigurationMissing(error)) {
            notifyToast({
              title: "No active configuration",
              description: "Activate a configuration for this workspace before reprocessing.",
              intent: "warning",
            });
            return;
          }
          notifyToast({
            title: "Reprocess failed",
            description: resolveApiErrorMessage(error, "Unable to start a new run."),
            intent: "danger",
          });
        });
    },
    [notifyToast, queryClient, workspaceId],
  );

  const toggleTagOnDocument = useCallback(
    (doc: DocumentEntry, tag: string) => {
      if (!doc.record) return;
      const hasTag = doc.tags.includes(tag);
      const patch = hasTag ? { remove: [tag] } : { add: [tag] };

      void patchWorkspaceDocumentTags(workspaceId, doc.record.id, patch)
        .then((updated) => {
          // Patch query cache in-place for immediate UI updates (no full refetch).
          queryClient.setQueryData(listKey, (existing: any) => {
            if (!existing?.pages) return existing;
            return {
              ...existing,
              pages: existing.pages.map((p: any) => ({
                ...p,
                items: (p.items ?? []).map((item: any) => (item.id === updated.id ? updated : item)),
              })),
            };
          });
        })
        .catch((error) => {
          notifyToast({
            title: "Tag update failed",
            description: error instanceof Error ? error.message : "Unable to update tags.",
            intent: "danger",
          });
        });
    },
    [listKey, notifyToast, queryClient, workspaceId],
  );

  const bulkAddTagPrompt = useCallback(() => {
    const tag = window.prompt("Add tag to selected documents:");
    const value = (tag ?? "").trim();
    if (!value) return;

    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;

    void patchWorkspaceDocumentTagsBatch(
      workspaceId,
      docs.map((doc) => doc.record!.id),
      { add: [value] },
    )
      .then(() => {
        notifyToast({ title: "Tags applied", description: `${value} added`, intent: "success" });
        queryClient.invalidateQueries({ queryKey: documentsV9Keys.workspace(workspaceId) });
      })
      .catch((error) => {
        notifyToast({
          title: "Bulk tag failed",
          description: error instanceof Error ? error.message : "Unable to apply tags.",
          intent: "danger",
        });
      });
  }, [notifyToast, queryClient, selectedIds, visibleDocuments, workspaceId]);

  const bulkDownloadOriginals = useCallback(() => {
    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;
    docs.forEach((d) => {
      void downloadWorkspaceDocumentOriginal(workspaceId, d.record!.id, d.name).catch(() => undefined);
    });
    notifyToast({ title: "Downloads started", description: `${docs.length} originals`, intent: "success" });
  }, [notifyToast, selectedIds, visibleDocuments, workspaceId]);

  const bulkReprocess = useCallback(() => {
    const docs = visibleDocuments.filter((d) => selectedIds.has(d.id) && d.record);
    if (docs.length === 0) return;
    docs.forEach((d) => reprocessDocument(d));
  }, [reprocessDocument, selectedIds, visibleDocuments]);

  const refreshDocuments = useCallback(() => void documentsQuery.refetch(), [documentsQuery]);
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

  return {
    state: {
      viewMode,
      groupBy,
      hideEmptyColumns,
      sort,
      search,
      filters,
      activeViewKey,
      savedViews,
      selectedIds,
      activeId,
      previewOpen,
      activeRunId,
      activeSheetId,
    },
    derived: {
      now,
      documents,
      visibleDocuments,
      activeDocument,
      boardColumns,
      statusCounts,
      isLoading: documentsQuery.isLoading,
      isError: documentsQuery.isError,
      hasNextPage: Boolean(documentsQuery.hasNextPage),
      isFetchingNextPage: documentsQuery.isFetchingNextPage,
      runs,
      runsLoading: runsQuery.isFetching,
      activeRun,
      outputUrl,
      workbook: workbookQuery.data ?? null,
      workbookLoading: workbookQuery.isLoading,
      workbookError: workbookQuery.isError,
      showNoDocuments,
      showNoResults,
      allVisibleSelected,
      activeViewLabel,
      showSaveView,
    },
    refs: { searchRef, fileInputRef },
    actions: {
      setSearch: setSearchValue,
      setViewMode: setViewModeValue,
      setGroupBy: setGroupByValue,
      setHideEmptyColumns: setHideEmptyColumnsValue,
      setSort: setSortValue,

      toggleStatusFilter,
      toggleFileTypeFilter,
      setTagMode,
      toggleTagFilter,
      clearFilters,

      selectBuiltInView,
      selectSavedView,
      saveCurrentView,
      deleteSavedView,

      toggleSelect,
      selectAllVisible,
      clearSelection,

      openPreview,
      closePreview,

      setActiveRunId: setActiveRunIdValue,
      setActiveSheetId: setActiveSheetIdValue,

      handleUploadClick,
      handleFileInputChange,

      downloadOriginal,
      downloadOutputFromRow,
      downloadOutputFromPreview,

      reprocessDocument,
      toggleTagOnDocument,

      bulkAddTagPrompt,
      bulkDownloadOriginals,
      bulkReprocess,

      refreshDocuments,
      loadMore,
      handleKeyNavigate,
    },
  };
}

function statusLabel(status: DocumentStatus) {
  switch (status) {
    case "ready":
      return "Ready";
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
