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

import { useNotifications } from "@shared/notifications";
import { uploadWorkspaceDocument, type DocumentUploadResponse } from "@shared/documents";
import { useUploadQueue } from "@shared/uploads/queue";
import { fetchRun, runOutputUrl, type RunResource } from "@shared/runs/api";

import {
  DOCUMENTS_PAGE_SIZE,
  documentsV9Keys,
  downloadProcessedOutput,
  buildDocumentEntry,
  buildUploadEntry,
  fetchWorkbookPreview,
  fetchWorkspaceDocuments,
} from "../data";
import type {
  BoardColumn,
  BoardGroup,
  DocumentEntry,
  DocumentPage,
  DocumentStatus,
  ViewMode,
  WorkbookPreview,
} from "../types";

type StatusFilterValue = DocumentStatus | "all";

type WorkbenchState = {
  viewMode: ViewMode;
  groupBy: BoardGroup;
  boardHideEmpty: boolean;

  search: string;
  statusFilter: StatusFilterValue;

  selectedIds: Set<string>;
  activeId: string | null;
  previewOpen: boolean;
  activeSheetId: string | null;
};

type WorkbenchDerived = {
  now: number;

  documents: DocumentEntry[];
  filteredDocuments: DocumentEntry[]; // search-filtered (before status filter)
  sortedDocuments: DocumentEntry[]; // search + status-filtered + sorted

  statusCounts: Record<DocumentStatus, number>;
  filteredTotal: number;

  selectedCount: number;
  selectedReadyCount: number;

  activeDocument: DocumentEntry | null;
  boardColumns: BoardColumn[];

  isLoading: boolean;
  isError: boolean;
  isRefreshing: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  lastSyncedAt: number | null;

  activeRun: RunResource | null;
  runLoading: boolean;
  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;

  showNoDocuments: boolean;
  showNoResults: boolean;
  allVisibleSelected: boolean;

  hasFilters: boolean;
};

type WorkbenchRefs = {
  searchRef: MutableRefObject<HTMLInputElement | null>;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
};

type WorkbenchActions = {
  setSearch: (value: string) => void;

  setStatusFilter: (value: StatusFilterValue) => void;
  clearFilters: () => void;

  setViewMode: (value: ViewMode) => void;
  setGroupBy: (value: BoardGroup) => void;
  setBoardHideEmpty: (value: boolean) => void;

  toggleSelect: (id: string) => void;
  selectAllVisible: () => void;
  clearSelection: () => void;

  openPreview: (id: string) => void;
  closePreview: () => void;

  setActiveSheetId: (id: string) => void;
  handleUploadClick: () => void;
  handleFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;

  downloadDocument: (doc: DocumentEntry | null) => void;
  downloadSelected: () => void;

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

const BOARD_UNASSIGNED_ID = "__board_unassigned__";
const BOARD_UNTAGGED_ID = "__board_untagged__";
const STATUS_ORDER: DocumentStatus[] = ["queued", "processing", "ready", "failed", "archived"];

const STORAGE_KEYS = {
  viewMode: "ade:documentsV9:viewMode",
  groupBy: "ade:documentsV9:groupBy",
  boardHideEmpty: "ade:documentsV9:boardHideEmpty",
  statusFilter: "ade:documentsV9:statusFilter",
} as const;

function safeReadStorage(key: string): string | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWriteStorage(key: string, value: string) {
  try {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(key, value);
  } catch {
    // ignore
  }
}

function parseStatusFilter(value: string | null): StatusFilterValue {
  if (!value) return "all";
  if (value === "all") return "all";
  if (value === "queued" || value === "processing" || value === "ready" || value === "failed" || value === "archived") {
    return value;
  }
  return "all";
}

function parseBoardGroup(value: string | null): BoardGroup {
  if (value === "status" || value === "tag" || value === "uploader") return value;
  return "status";
}

function parseViewMode(value: string | null): ViewMode {
  if (value === "grid" || value === "board") return value;
  return "grid";
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

  const [viewMode, setViewMode] = useState<ViewMode>(() => parseViewMode(safeReadStorage(STORAGE_KEYS.viewMode)));
  const [groupBy, setGroupBy] = useState<BoardGroup>(() => parseBoardGroup(safeReadStorage(STORAGE_KEYS.groupBy)));
  const [boardHideEmpty, setBoardHideEmpty] = useState<boolean>(() => safeReadStorage(STORAGE_KEYS.boardHideEmpty) !== "0");

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>(() =>
    parseStatusFilter(safeReadStorage(STORAGE_KEYS.statusFilter)),
  );

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const searchRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadCreatedAtRef = useRef(new Map<string, number>());
  const handledUploadsRef = useRef(new Set<string>());

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "/") {
        const target = event.target as HTMLElement | null;
        if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
          return;
        }
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === "Escape") {
        setPreviewOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Persist view preferences
  useEffect(() => safeWriteStorage(STORAGE_KEYS.viewMode, viewMode), [viewMode]);
  useEffect(() => safeWriteStorage(STORAGE_KEYS.groupBy, groupBy), [groupBy]);
  useEffect(() => safeWriteStorage(STORAGE_KEYS.boardHideEmpty, boardHideEmpty ? "1" : "0"), [boardHideEmpty]);
  useEffect(() => safeWriteStorage(STORAGE_KEYS.statusFilter, statusFilter), [statusFilter]);

  const startUpload = useCallback(
    (
      file: File,
      handlers: { onProgress: (progress: { loaded: number; total: number | null; percent: number | null }) => void },
    ) => uploadWorkspaceDocument(workspaceId, file, { onProgress: handlers.onProgress }),
    [workspaceId],
  );

  const uploadQueue = useUploadQueue<DocumentUploadResponse>({
    startUpload,
  });

  const sort = "-created_at";
  const documentsQuery = useInfiniteQuery<DocumentPage>({
    queryKey: documentsV9Keys.list(workspaceId, sort),
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort,
          page: typeof pageParam === "number" ? pageParam : 1,
          pageSize: DOCUMENTS_PAGE_SIZE,
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
        notifyToast({
          title: "Upload failed",
          description: item.error,
          intent: "danger",
        });
      }
    });
  }, [notifyToast, queryClient, uploadQueue.items, workspaceId]);

  const uploadEntries = useMemo(() => {
    const entries: DocumentEntry[] = [];
    uploadQueue.items.forEach((item) => {
      const createdAt = uploadCreatedAtRef.current.get(item.id) ?? Date.now();
      if (item.status === "succeeded" && item.response) {
        if (documentsById.has(item.response.id)) {
          return;
        }
        entries.push(buildDocumentEntry(item.response, { upload: item }));
        return;
      }
      entries.push(buildUploadEntry(item, currentUserLabel, createdAt));
    });
    return entries;
  }, [currentUserLabel, documentsById, uploadQueue.items]);

  const apiEntries = useMemo(() => documentsRaw.map((doc) => buildDocumentEntry(doc)), [documentsRaw]);
  const documents = useMemo(() => [...uploadEntries, ...apiEntries], [uploadEntries, apiEntries]);
  const documentsByEntryId = useMemo(() => new Map(documents.map((doc) => [doc.id, doc])), [documents]);

  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      previous.forEach((id) => {
        if (documentsByEntryId.has(id)) {
          next.add(id);
        }
      });
      return next;
    });
  }, [documentsByEntryId]);

  // If the active doc disappears, clear active + close preview (prevents phantom preview)
  useEffect(() => {
    if (!activeId) {
      return;
    }
    if (!documentsByEntryId.has(activeId)) {
      setActiveId(null);
      setPreviewOpen(false);
    }
  }, [activeId, documentsByEntryId]);

  const activeDocument = useMemo(
    () => (activeId ? documentsByEntryId.get(activeId) ?? null : null),
    [activeId, documentsByEntryId],
  );

  const activeRunId = activeDocument?.record?.last_run?.run_id ?? null;
  const runQuery = useQuery<RunResource | null>({
    queryKey: activeRunId ? documentsV9Keys.run(activeRunId) : [...documentsV9Keys.root(), "run", "none"],
    queryFn: ({ signal }) => (activeRunId ? fetchRun(activeRunId, signal) : Promise.resolve(null)),
    enabled: Boolean(activeRunId),
    staleTime: 15_000,
    refetchInterval: (data) => {
      const status = data?.status ?? null;
      if (status === "running" || status === "queued") {
        return 3000;
      }
      return false;
    },
  });

  const outputUrl = runQuery.data ? runOutputUrl(runQuery.data) : null;
  const workbookQuery = useQuery<WorkbookPreview>({
    queryKey: outputUrl ? documentsV9Keys.workbook(outputUrl) : [...documentsV9Keys.root(), "workbook", "none"],
    queryFn: ({ signal }) =>
      outputUrl ? fetchWorkbookPreview(outputUrl, signal) : Promise.reject(new Error("No output URL")),
    enabled: Boolean(outputUrl),
    staleTime: 30_000,
  });

  useEffect(() => {
    setActiveSheetId(null);
  }, [activeDocument?.id]);

  useEffect(() => {
    if (workbookQuery.data?.sheets.length) {
      setActiveSheetId(workbookQuery.data.sheets[0].name);
    }
  }, [workbookQuery.data?.sheets]);

  const normalizedSearch = search.trim().toLowerCase();

  // Search-filtered (for counts + status breakdown)
  const filteredDocuments = useMemo(() => {
    if (!normalizedSearch) {
      return documents;
    }
    return documents.filter((doc) => {
      const haystack = [doc.name, doc.uploader ?? "", doc.tags.join(" ")].join(" ").toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [documents, normalizedSearch]);

  const statusCounts = useMemo(() => {
    const counts: Record<DocumentStatus, number> = {
      queued: 0,
      processing: 0,
      ready: 0,
      failed: 0,
      archived: 0,
    };
    filteredDocuments.forEach((doc) => {
      counts[doc.status] += 1;
    });
    return counts;
  }, [filteredDocuments]);

  // Apply status filter
  const statusFilteredDocuments = useMemo(() => {
    if (statusFilter === "all") return filteredDocuments;
    return filteredDocuments.filter((doc) => doc.status === statusFilter);
  }, [filteredDocuments, statusFilter]);

  const sortedDocuments = useMemo(
    () => [...statusFilteredDocuments].sort((a, b) => b.createdAt - a.createdAt || a.name.localeCompare(b.name)),
    [statusFilteredDocuments],
  );

  // Prevent opening preview for a doc that is not currently visible (e.g. filters changed)
  useEffect(() => {
    if (!activeId) return;
    if (previewOpen) return;
    const visibleIds = new Set(sortedDocuments.map((doc) => doc.id));
    if (!visibleIds.has(activeId)) {
      setActiveId(null);
    }
  }, [activeId, previewOpen, sortedDocuments]);

  const boardColumns = useMemo<BoardColumn[]>(() => {
    if (groupBy === "status") {
      return STATUS_ORDER.map((status) => ({
        id: status,
        label: statusLabel(status),
        items: sortedDocuments.filter((doc) => doc.status === status),
      }));
    }
    if (groupBy === "tag") {
      const tagSet = new Set<string>();
      sortedDocuments.forEach((doc) => doc.tags.forEach((tag) => tagSet.add(tag)));
      const tags = Array.from(tagSet).sort((a, b) => a.localeCompare(b));
      const columns = tags.map((tag) => ({
        id: tag,
        label: tag,
        items: sortedDocuments.filter((doc) => doc.tags.includes(tag)),
      }));
      columns.push({
        id: BOARD_UNTAGGED_ID,
        label: "Untagged",
        items: sortedDocuments.filter((doc) => doc.tags.length === 0),
      });
      return columns;
    }
    const uploaderSet = new Set<string>();
    sortedDocuments.forEach((doc) => {
      if (doc.uploader) {
        uploaderSet.add(doc.uploader);
      }
    });
    const uploaders = Array.from(uploaderSet).sort((a, b) => a.localeCompare(b));
    const columns = uploaders.map((uploader) => ({
      id: uploader,
      label: uploader,
      items: sortedDocuments.filter((doc) => doc.uploader === uploader),
    }));
    columns.push({
      id: BOARD_UNASSIGNED_ID,
      label: "Unassigned",
      items: sortedDocuments.filter((doc) => !doc.uploader),
    });
    return columns;
  }, [groupBy, sortedDocuments]);

  const selectableIds = useMemo(
    () => sortedDocuments.filter((doc) => doc.record).map((doc) => doc.id),
    [sortedDocuments],
  );
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));

  const showNoDocuments = documents.length === 0;
  const showNoResults = documents.length > 0 && sortedDocuments.length === 0;

  const hasFilters = Boolean(search.trim().length > 0 || statusFilter !== "all");

  const selectedCount = selectedIds.size;

  const selectedReadyCount = useMemo(() => {
    let count = 0;
    selectedIds.forEach((id) => {
      const doc = documentsByEntryId.get(id);
      if (!doc?.record) return;
      if (doc.status !== "ready") return;
      if (!doc.record.last_run?.run_id) return;
      count += 1;
    });
    return count;
  }, [documentsByEntryId, selectedIds]);

  const setSearchValue = useCallback((value: string) => setSearch(value), []);
  const setStatusFilterValue = useCallback((value: StatusFilterValue) => setStatusFilter(value), []);

  const clearFilters = useCallback(() => {
    setSearch("");
    setStatusFilter("all");
  }, []);

  const setViewModeValue = useCallback((value: ViewMode) => setViewMode(value), []);
  const setGroupByValue = useCallback((value: BoardGroup) => setGroupBy(value), []);
  const setBoardHideEmptyValue = useCallback((value: boolean) => setBoardHideEmpty(value), []);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAllVisible = useCallback(() => {
    setSelectedIds(new Set(selectableIds));
  }, [selectableIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const openPreview = useCallback((id: string) => {
    setActiveId(id);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => {
    setPreviewOpen(false);
  }, []);

  const setActiveSheetIdValue = useCallback((id: string) => {
    setActiveSheetId(id);
  }, []);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) {
        return;
      }
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

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      handleFiles(event.target.files);
      event.target.value = "";
    },
    [handleFiles],
  );

  const downloadDocument = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record) {
        return;
      }
      if (doc.status !== "ready") {
        notifyToast({
          title: "Output not ready",
          description: "Processing needs to finish before downloading the normalized XLSX.",
          intent: "warning",
        });
        return;
      }
      if (!doc.record.last_run?.run_id) {
        notifyToast({
          title: "No processed output",
          description: "This document does not have a completed run to download yet.",
          intent: "warning",
        });
        return;
      }
      void downloadProcessedOutput(doc.record.last_run.run_id, doc.name)
        .then((filename) => {
          notifyToast({
            title: "Download started",
            description: filename,
            intent: "success",
          });
        })
        .catch((error) => {
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : "Unable to download the processed XLSX.",
            intent: "danger",
          });
        });
    },
    [notifyToast],
  );

  const downloadSelected = useCallback(() => {
    const selectedDocs: DocumentEntry[] = [];
    selectedIds.forEach((id) => {
      const doc = documentsByEntryId.get(id);
      if (doc) selectedDocs.push(doc);
    });

    const readyDocs = selectedDocs.filter(
      (doc) => doc.record && doc.status === "ready" && Boolean(doc.record.last_run?.run_id),
    );

    if (readyDocs.length === 0) {
      notifyToast({
        title: "Nothing to download",
        description: "Select at least one Ready document with a processed output.",
        intent: "warning",
      });
      return;
    }

    notifyToast({
      title: "Starting downloads",
      description: `${readyDocs.length} processed file${readyDocs.length === 1 ? "" : "s"}`,
      intent: "success",
    });

    void (async () => {
      for (const doc of readyDocs) {
        const runId = doc.record?.last_run?.run_id;
        if (!runId) continue;
        try {
          await downloadProcessedOutput(runId, doc.name);
        } catch (error) {
          notifyToast({
            title: "Download failed",
            description: error instanceof Error ? error.message : `Unable to download ${doc.name}.`,
            intent: "danger",
          });
        }
      }
    })();
  }, [documentsByEntryId, notifyToast, selectedIds]);

  const refreshDocuments = useCallback(() => {
    void documentsQuery.refetch();
  }, [documentsQuery]);

  const loadMore = useCallback(() => {
    if (documentsQuery.hasNextPage) {
      void documentsQuery.fetchNextPage();
    }
  }, [documentsQuery]);

  const handleKeyNavigate = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (sortedDocuments.length === 0) {
        return;
      }

      // Only treat Enter/Space at the container level (not when focused on a row/checkbox).
      const isContainerTarget = event.target === event.currentTarget;

      if ((event.key === "Enter" || event.key === " ") && isContainerTarget) {
        event.preventDefault();
        const nextId = activeId ?? sortedDocuments[0].id;
        setActiveId(nextId);
        setPreviewOpen(true);
        return;
      }

      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
        return;
      }

      event.preventDefault();
      const currentIndex = activeId ? sortedDocuments.findIndex((doc) => doc.id === activeId) : -1;

      if (currentIndex < 0) {
        setActiveId(sortedDocuments[0].id);
        return;
      }

      const nextIndex =
        event.key === "ArrowDown"
          ? Math.min(sortedDocuments.length - 1, currentIndex + 1)
          : Math.max(0, currentIndex - 1);

      setActiveId(sortedDocuments[nextIndex].id);
    },
    [activeId, sortedDocuments],
  );

  const lastSyncedAt = documentsQuery.dataUpdatedAt ? documentsQuery.dataUpdatedAt : null;

  return {
    state: {
      viewMode,
      groupBy,
      boardHideEmpty,
      search,
      statusFilter,
      selectedIds,
      activeId,
      previewOpen,
      activeSheetId,
    },
    derived: {
      now,
      documents,
      filteredDocuments,
      sortedDocuments,

      statusCounts,
      filteredTotal: filteredDocuments.length,

      selectedCount,
      selectedReadyCount,

      activeDocument,
      boardColumns,
      isLoading: documentsQuery.isLoading,
      isError: documentsQuery.isError,
      isRefreshing: documentsQuery.isFetching,
      hasNextPage: Boolean(documentsQuery.hasNextPage),
      isFetchingNextPage: documentsQuery.isFetchingNextPage,
      lastSyncedAt,

      activeRun: runQuery.data ?? null,
      runLoading: runQuery.isFetching,
      outputUrl,
      workbook: workbookQuery.data ?? null,
      workbookLoading: workbookQuery.isLoading,
      workbookError: workbookQuery.isError,

      showNoDocuments,
      showNoResults,
      allVisibleSelected,
      hasFilters,
    },
    refs: {
      searchRef,
      fileInputRef,
    },
    actions: {
      setSearch: setSearchValue,

      setStatusFilter: setStatusFilterValue,
      clearFilters,

      setViewMode: setViewModeValue,
      setGroupBy: setGroupByValue,
      setBoardHideEmpty: setBoardHideEmptyValue,

      toggleSelect,
      selectAllVisible,
      clearSelection,

      openPreview,
      closePreview,

      setActiveSheetId: setActiveSheetIdValue,
      handleUploadClick,
      handleFileInputChange,

      downloadDocument,
      downloadSelected,

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
