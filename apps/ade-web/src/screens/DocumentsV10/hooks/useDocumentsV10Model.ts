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
import { createRun } from "@shared/runs/api";

import type { RunResource } from "@schema";

import {
  DOCUMENTS_PAGE_SIZE,
  buildDocumentEntry,
  createRunForDocument,
  documentsV10Keys,
  downloadOriginalDocument,
  downloadRunOutput,
  downloadRunOutputById,
  fetchWorkbookPreview,
  fetchWorkspaceDocumentById,
  fetchWorkspaceDocuments,
  fetchWorkspaceMembers,
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
  DocumentComment,
  DocumentEntry,
  DocumentsFilters,
  DocumentPage,
  DocumentStatus,
  SavedView,
  ViewMode,
  WorkbookPreview,
  WorkspacePerson,
} from "../types";
import { copyToClipboard, fileTypeFromName, formatBytes, parseTimestamp, shortId } from "../utils";

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

  // Output preview
  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;

  // Empty states
  showNoDocuments: boolean;
  showNoResults: boolean;
  allVisibleSelected: boolean;

  // Saved views
  savedViews: SavedView[];

  // Notes
  activeComments: DocumentComment[];

  // Counts for sidebar
  counts: {
    total: number;
    mine: number;
    unassigned: number;
    ready: number;
    processing: number;
    failed: number;
  };
};

type WorkbenchRefs = {
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
};

type WorkbenchActions = {
  setSearch: (value: string) => void;
  setViewMode: (value: ViewMode) => void;
  setGroupBy: (value: BoardGroup) => void;

  toggleSelect: (id: string) => void;
  selectAllVisible: () => void;
  clearSelection: () => void;

  openPreview: (id: string) => void;
  closePreview: () => void;

  setActiveSheetId: (id: string) => void;

  handleUploadClick: () => void;
  handleFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;

  refreshDocuments: () => void;
  loadMore: () => void;

  handleKeyNavigate: (event: KeyboardEvent<HTMLDivElement>) => void;

  // Filters & views
  setFilters: (next: DocumentsFilters) => void;
  setBuiltInView: (id: string) => void;
  selectSavedView: (viewId: string) => void;
  openSaveView: () => void;
  closeSaveView: () => void;
  saveView: (name: string) => void;
  deleteView: (viewId: string) => void;

  // Tags (persisted)
  updateTagsOptimistic: (documentId: string, nextTags: string[]) => void;

  // Assignment (local-first)
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

  // Bulk actions
  bulkAddTagPrompt: () => void;
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

const DEFAULT_FILTERS: DocumentsFilters = {
  statuses: [],
  fileTypes: [],
  tags: [],
  tagMode: "any",
  assignees: [],
};

const UNASSIGNED_KEY = "__unassigned__";

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
  const raw = window.localStorage.getItem(`ade.documents.v10.views.${workspaceId}`);
  const parsed = safeJsonParse<SavedView[]>(raw);
  if (!parsed) return [];
  return parsed.map((v) => ({
    ...v,
    filters: {
      ...DEFAULT_FILTERS,
      ...(v.filters ?? {}),
      tagMode: v.filters?.tagMode ?? "any",
      assignees: v.filters?.assignees ?? [],
    },
  }));
}

function storeSavedViews(workspaceId: string, views: SavedView[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(`ade.documents.v10.views.${workspaceId}`, JSON.stringify(views));
}

function loadAssignments(workspaceId: string): Record<string, string | null> {
  if (typeof window === "undefined") return {};
  const raw = window.localStorage.getItem(`ade.documents.v10.assignments.${workspaceId}`);
  const parsed = safeJsonParse<Record<string, string | null>>(raw);
  return parsed ?? {};
}

function storeAssignments(workspaceId: string, map: Record<string, string | null>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(`ade.documents.v10.assignments.${workspaceId}`, JSON.stringify(map));
}

function loadComments(workspaceId: string): Record<string, DocumentComment[]> {
  if (typeof window === "undefined") return {};
  const raw = window.localStorage.getItem(`ade.documents.v10.comments.${workspaceId}`);
  const parsed = safeJsonParse<Record<string, DocumentComment[]>>(raw);
  return parsed ?? {};
}

function storeComments(workspaceId: string, map: Record<string, DocumentComment[]>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(`ade.documents.v10.comments.${workspaceId}`, JSON.stringify(map));
}

export function useDocumentsV10Model({
  workspaceId,
  currentUserLabel,
  currentUserId,
}: {
  workspaceId: string;
  currentUserLabel: string;
  currentUserId: string;
}): WorkbenchModel {
  const { notifyToast } = useNotifications();
  const queryClient = useQueryClient();

  const currentUserKey = `user:${currentUserId}`;

  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [groupBy, setGroupBy] = useState<BoardGroup>("status");
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const [filters, setFilters] = useState<DocumentsFilters>(DEFAULT_FILTERS);
  const [activeViewId, setActiveViewId] = useState<string>("all");
  const [saveViewOpen, setSaveViewOpen] = useState(false);

  const [savedViews, setSavedViews] = useState<SavedView[]>(() => loadSavedViews(workspaceId));
  const [assignments, setAssignments] = useState<Record<string, string | null>>(() => loadAssignments(workspaceId));
  const [commentsByDocId, setCommentsByDocId] = useState<Record<string, DocumentComment[]>>(() => loadComments(workspaceId));

  const [now, setNow] = useState(() => Date.now());

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadCreatedAtRef = useRef(new Map<string, number>());
  const handledUploadsRef = useRef(new Set<string>());
  const runOnUploadHandledRef = useRef(new Set<string>());

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    setSavedViews(loadSavedViews(workspaceId));
    setAssignments(loadAssignments(workspaceId));
    setCommentsByDocId(loadComments(workspaceId));
  }, [workspaceId]);

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
  const listKey = useMemo(() => documentsV10Keys.list(workspaceId, sort), [sort, workspaceId]);

  const documentsQuery = useInfiniteQuery<DocumentPage>({
    queryKey: listKey,
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
        queryClient.invalidateQueries({ queryKey: documentsV10Keys.workspace(workspaceId) });
      }
      if (item.status === "failed" && item.error && !handledUploadsRef.current.has(`fail-${item.id}`)) {
        handledUploadsRef.current.add(`fail-${item.id}`);
        notifyToast({ title: "Upload failed", description: item.error, intent: "danger" });
      }
    });
  }, [notifyToast, queryClient, uploadQueue.items, workspaceId]);

  useEffect(() => {
    uploadQueue.items.forEach((item) => {
      if (item.status !== "succeeded" || !item.response?.id) return;
      if (item.response.status && item.response.status !== "uploaded") return;
      if (runOnUploadHandledRef.current.has(item.id)) return;
      runOnUploadHandledRef.current.add(item.id);

      void createRun(workspaceId, { input_document_id: item.response.id })
        .then(() => {
          queryClient.invalidateQueries({ queryKey: documentsV10Keys.workspace(workspaceId) });
        })
        .catch((error) => {
          const message = error instanceof Error ? error.message : "Unable to start a run for this upload.";
          notifyToast({ title: "Run not started", description: message, intent: "warning" });
        });
    });
  }, [notifyToast, queryClient, uploadQueue.items, workspaceId]);

  const uploadEntries = useMemo(() => {
    const entries: DocumentEntry[] = [];
    uploadQueue.items.forEach((item) => {
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
        stage: item.status === "failed" ? "Upload failed" : item.status === "uploading" ? "Uploading" : "Queued for upload",
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

        assigneeKey: assignments[item.id] ?? null,
        assigneeLabel: null,
        commentCount: (commentsByDocId[item.id] ?? []).length,

        record: item.response,
        upload: item,
      });
    });
    return entries;
  }, [assignments, commentsByDocId, currentUserLabel, documentsById, uploadQueue.items]);

  const apiEntriesBase = useMemo(() => documentsRaw.map((doc) => buildDocumentEntry(doc)), [documentsRaw]);

  const membersQuery = useQuery({
    queryKey: documentsV10Keys.members(workspaceId),
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

    apiEntriesBase.forEach((d) => {
      if (d.uploader) {
        const key = `label:${d.uploader}`;
        if (!set.has(key)) set.set(key, { key, label: d.uploader, kind: "label" });
      }
    });

    return Array.from(set.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [apiEntriesBase, currentUserId, currentUserKey, currentUserLabel, membersQuery.data?.items]);

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
        ? documentsV10Keys.document(workspaceId, activeId)
        : [...documentsV10Keys.root(), "document", "none"],
    queryFn: ({ signal }) => (activeId ? fetchWorkspaceDocumentById(workspaceId, activeId, signal) : Promise.reject()),
    enabled: Boolean(activeId && workspaceId) && !documentsById.has(activeId ?? ""),
    staleTime: 30_000,
  });

  const pinnedActiveEntry = useMemo(() => {
    if (!activeDocQuery.data) return null;
    return buildDocumentEntry(activeDocQuery.data);
  }, [activeDocQuery.data]);

  const baseDocuments = useMemo(() => {
    const all = [...uploadEntries, ...apiEntriesBase];
    if (pinnedActiveEntry && !all.some((d) => d.id === pinnedActiveEntry.id)) {
      return [pinnedActiveEntry, ...all];
    }
    return all;
  }, [apiEntriesBase, pinnedActiveEntry, uploadEntries]);

  const documents = useMemo<DocumentEntry[]>(() => {
    return baseDocuments.map((doc) => {
      const overrideAssignee = assignments[doc.id] ?? null;
      const assigneeKey = overrideAssignee ?? doc.assigneeKey ?? null;
      const commentCount = (commentsByDocId[doc.id] ?? []).length;

      return {
        ...doc,
        assigneeKey,
        assigneeLabel: assigneeLabelForKey(assigneeKey),
        commentCount,
      };
    });
  }, [assignments, assigneeLabelForKey, baseDocuments, commentsByDocId]);

  const documentsByEntryId = useMemo(() => new Map(documents.map((d) => [d.id, d])), [documents]);

  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      previous.forEach((id) => {
        if (documentsByEntryId.has(id)) next.add(id);
      });
      return next;
    });
  }, [documentsByEntryId]);

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

  const visibleDocuments = useMemo(() => {
    const searchValue = search.trim().toLowerCase();
    const hasSearch = searchValue.length >= 2;

    return documents.filter((doc) => {
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

      if (filters.statuses.length > 0 && !filters.statuses.includes(doc.status)) return false;
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
  }, [documents, filters, search]);

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
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));

  const showNoDocuments = documents.length === 0;
  const showNoResults = documents.length > 0 && visibleDocuments.length === 0;

  const counts = useMemo(() => {
    const mine = documents.filter((d) => d.assigneeKey === currentUserKey).length;
    const unassigned = documents.filter((d) => !d.assigneeKey).length;
    const ready = documents.filter((d) => d.status === "ready").length;
    const processing = documents.filter((d) => d.status === "processing" || d.status === "queued").length;
    const failed = documents.filter((d) => d.status === "failed").length;
    return { total: documents.length, mine, unassigned, ready, processing, failed };
  }, [currentUserKey, documents]);

  const activeComments = useMemo(() => {
    if (!activeDocument) return [];
    return commentsByDocId[activeDocument.id] ?? [];
  }, [activeDocument, commentsByDocId]);

  const activeDocumentIdForRuns = activeDocument?.record?.id ?? null;

  const runsQuery = useQuery({
    queryKey: activeDocumentIdForRuns
      ? documentsV10Keys.runsForDocument(workspaceId, activeDocumentIdForRuns)
      : [...documentsV10Keys.workspace(workspaceId), "runs", "none"],
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

  useEffect(() => {
    if (!previewOpen) return;
    setSelectedRunId((prev) => {
      const existing = prev && runs.some((r) => r.id === prev) ? prev : null;
      if (existing) return existing;

      const preferred = activeDocument?.record?.last_run?.run_id ?? null;
      if (preferred && runs.some((r) => r.id === preferred)) return preferred;

      return runs[0]?.id ?? null;
    });
  }, [activeDocument?.id, previewOpen, runs]);

  const activeRun = useMemo(() => {
    if (!selectedRunId) return null;
    return runs.find((r) => r.id === selectedRunId) ?? null;
  }, [runs, selectedRunId]);

  const outputUrl = useMemo(() => {
    if (!activeRun) return null;
    if (!runHasDownloadableOutput(activeRun)) return null;
    return runOutputDownloadUrl(activeRun);
  }, [activeRun]);

  const workbookQuery = useQuery<WorkbookPreview>({
    queryKey: outputUrl ? documentsV10Keys.workbook(outputUrl) : [...documentsV10Keys.root(), "workbook", "none"],
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

  const setSearchValue = useCallback((value: string) => setSearch(value), []);
  const setViewModeValue = useCallback((value: ViewMode) => setViewMode(value), []);
  const setGroupByValue = useCallback((value: BoardGroup) => setGroupBy(value), []);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllVisible = useCallback(() => setSelectedIds(new Set(selectableIds)), [selectableIds]);
  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const openPreview = useCallback((id: string) => {
    setActiveId(id);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => setPreviewOpen(false), []);

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

  const setFiltersValue = useCallback(
    (next: DocumentsFilters) => {
      setFilters(next);
      const hasSearch = search.trim().length >= 2;
      const isDefault =
        next.statuses.length === 0 &&
        next.fileTypes.length === 0 &&
        next.tags.length === 0 &&
        next.assignees.length === 0;
      setActiveViewId(!hasSearch && isDefault ? "all" : "custom");
    },
    [search],
  );

  const setBuiltInView = useCallback(
    (id: string) => {
      setActiveViewId(id);
      setFilters((prev) => {
        const cleared: DocumentsFilters = {
          ...prev,
          statuses: [],
          fileTypes: [],
          tags: [],
          tagMode: "any",
          assignees: [],
        };

        switch (id) {
          case "mine":
            return { ...cleared, assignees: [currentUserKey] };
          case "unassigned":
            return { ...cleared, assignees: [UNASSIGNED_KEY] };
          case "ready":
            return { ...cleared, statuses: ["ready"] };
          case "processing":
            return { ...cleared, statuses: ["queued", "processing"] };
          case "failed":
            return { ...cleared, statuses: ["failed"] };
          case "all":
          default:
            return cleared;
        }
      });
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
        setActiveViewId("all");
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
          queryClient.invalidateQueries({ queryKey: documentsV10Keys.document(workspaceId, updated.id) });
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
      setAssignments((prev) => {
        const next = { ...prev, [documentId]: assigneeKey };
        storeAssignments(workspaceId, next);
        return next;
      });
      notifyToast({
        title: "Assignment updated",
        description: assigneeKey ? (peopleByKey.get(assigneeKey)?.label ?? assigneeKey) : "Unassigned",
        intent: "success",
      });
    },
    [notifyToast, peopleByKey, workspaceId],
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
          queryClient.invalidateQueries({ queryKey: documentsV10Keys.workspace(workspaceId) });
        })
        .catch((error) =>
          notifyToast({
            title: "Reprocess failed",
            description: error instanceof Error ? error.message : "Unable to reprocess.",
            intent: "danger",
          }),
        );
    },
    [activeRun?.configuration_id, notifyToast, queryClient, workspaceId],
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
        queryClient.invalidateQueries({ queryKey: documentsV10Keys.workspace(workspaceId) });
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
      outputUrl,
      workbook: workbookQuery.data ?? null,
      workbookLoading: workbookQuery.isLoading,
      workbookError: workbookQuery.isError,
      showNoDocuments,
      showNoResults,
      allVisibleSelected,
      savedViews,
      activeComments,
      counts,
    },
    refs: {
      fileInputRef,
    },
    actions: {
      setSearch: setSearchValue,
      setViewMode: setViewModeValue,
      setGroupBy: setGroupByValue,
      toggleSelect,
      selectAllVisible,
      clearSelection,
      openPreview,
      closePreview,
      setActiveSheetId: setActiveSheetIdValue,
      handleUploadClick,
      handleFileInputChange,
      refreshDocuments,
      loadMore,
      handleKeyNavigate,
      setFilters: setFiltersValue,
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
      bulkAddTagPrompt,
      bulkDownloadOriginals,
      bulkDownloadOutputs,
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
