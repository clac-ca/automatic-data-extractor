import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  type MutableRefObject,
} from "react";
import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useNotifications } from "@shared/notifications";
import { client } from "@shared/api/client";
import { uploadWorkspaceDocument, patchDocumentTags, type DocumentUploadResponse } from "@shared/documents";
import { useUploadQueue, type UploadQueueItem } from "@shared/uploads/queue";
import { readPreferredWorkspaceId, useWorkspacesQuery, type WorkspaceProfile } from "@shared/workspaces";
import { fetchRun, runOutputUrl, type RunResource, type RunStatus } from "@shared/runs/api";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { Select } from "@ui/Select";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";
import type { components, paths } from "@schema";

type DocumentRecord = components["schemas"]["DocumentOut"];
type DocumentPage = components["schemas"]["DocumentPage"];
type ApiDocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentLastRun = components["schemas"]["DocumentLastRun"];
type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

type DocumentStatus = "queued" | "processing" | "ready" | "failed" | "archived";

type ViewMode = "grid" | "board";

type BoardGroup = "owner" | "tag" | "status";

type StatusFilter = "all" | "attention" | "processing" | "ready" | "failed" | "queued" | "archived";

type MappingHealth = {
  attention: number;
  unmapped: number;
  pending?: boolean;
};

type WorkbookSheet = {
  name: string;
  headers: string[];
  rows: string[][];
  totalRows: number;
  totalColumns: number;
  truncatedRows: boolean;
  truncatedColumns: boolean;
};

type WorkbookPreview = {
  sheets: WorkbookSheet[];
};

type DocumentError = {
  summary: string;
  detail: string;
  nextStep: string;
};

type DocumentHistoryItem = {
  id: string;
  label: string;
  at: number;
  tone?: "success" | "warning" | "danger" | "info";
};

type DocumentEntry = {
  id: string;
  name: string;
  status: DocumentStatus;
  owner: string | null;
  tags: string[];
  createdAt: number;
  updatedAt: number;
  size: string;
  progress?: number;
  stage?: string;
  etaMinutes?: number;
  error?: DocumentError;
  mapping: MappingHealth;
  history: DocumentHistoryItem[];
  record?: DocumentRecord;
  upload?: UploadQueueItem<DocumentUploadResponse>;
};

type UploadContext = {
  owner?: string | null;
  tag?: string | null;
  status?: DocumentStatus;
};

type SavedView = {
  id: string;
  name: string;
  filters: {
    search: string;
    status: StatusFilter;
    owner: string;
    tags: string[];
  };
  view: ViewMode;
  groupBy: BoardGroup;
};

type BoardColumn = {
  id: string;
  label: string;
  context: UploadContext;
  items: DocumentEntry[];
};

const OWNER_FILTER_ALL = "__all__";
const OWNER_FILTER_UNASSIGNED = "__unassigned__";
const BOARD_UNASSIGNED_ID = "__board_unassigned__";
const BOARD_UNTAGGED_ID = "__board_untagged__";
const STORAGE_KEY = "ade.documents.v8.savedViews";
const DOCUMENTS_PAGE_SIZE = 50;
const MAX_PREVIEW_ROWS = 24;
const MAX_PREVIEW_COLUMNS = 16;

const documentsV8Keys = {
  root: () => ["documents-v8"] as const,
  workspace: (workspaceId: string) => [...documentsV8Keys.root(), workspaceId] as const,
  list: (workspaceId: string, sort: string | null) =>
    [...documentsV8Keys.workspace(workspaceId), "list", { sort }] as const,
  run: (runId: string) => [...documentsV8Keys.root(), "run", runId] as const,
  workbook: (url: string) => [...documentsV8Keys.root(), "workbook", url] as const,
};

const STATUS_STYLES: Record<
  DocumentStatus,
  {
    label: string;
    pill: string;
    dot: string;
    text: string;
  }
> = {
  ready: {
    label: "Ready",
    pill: "border-emerald-200 bg-emerald-50 text-emerald-700",
    dot: "bg-emerald-500",
    text: "text-emerald-700",
  },
  processing: {
    label: "Processing",
    pill: "border-amber-200 bg-amber-50 text-amber-700",
    dot: "bg-amber-500",
    text: "text-amber-700",
  },
  failed: {
    label: "Failed",
    pill: "border-rose-200 bg-rose-50 text-rose-700",
    dot: "bg-rose-500",
    text: "text-rose-700",
  },
  queued: {
    label: "Queued",
    pill: "border-border bg-background text-muted-foreground",
    dot: "bg-muted-foreground",
    text: "text-muted-foreground",
  },
  archived: {
    label: "Archived",
    pill: "border-border bg-muted text-muted-foreground",
    dot: "bg-muted-foreground",
    text: "text-muted-foreground",
  },
};

const STATUS_FILTERS: readonly { id: StatusFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "attention", label: "Needs attention" },
  { id: "processing", label: "Processing" },
  { id: "ready", label: "Ready" },
  { id: "failed", label: "Failed" },
  { id: "queued", label: "Queued" },
  { id: "archived", label: "Archived" },
];

const BOARD_GROUPS: readonly { id: BoardGroup; label: string }[] = [
  { id: "owner", label: "Uploader" },
  { id: "tag", label: "Tag" },
  { id: "status", label: "Status" },
];

const numberFormatter = new Intl.NumberFormat("en-US");

export default function DocumentsV8Screen() {
  return (
    <RequireSession>
      <DocumentsV8Redirect />
    </RequireSession>
  );
}

function DocumentsV8Redirect() {
  const location = useLocation();
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces: WorkspaceProfile[] = workspacesQuery.data?.items ?? [];

  const preferredIds = [readPreferredWorkspaceId(), session.user.preferred_workspace_id].filter(
    (value): value is string => Boolean(value),
  );
  const preferredWorkspace = preferredIds
    .map((id) => workspaces.find((workspace) => workspace.id === id))
    .find((match) => Boolean(match));

  const targetWorkspace = preferredWorkspace ?? workspaces[0] ?? null;

  useEffect(() => {
    if (workspacesQuery.isLoading || workspacesQuery.isError) {
      return;
    }

    if (!targetWorkspace) {
      navigate("/workspaces", { replace: true });
      return;
    }

    const target = `/workspaces/${targetWorkspace.id}/documents-v8${location.search}${location.hash}`;
    navigate(target, { replace: true });
  }, [
    location.hash,
    location.search,
    navigate,
    targetWorkspace,
    workspacesQuery.isError,
    workspacesQuery.isLoading,
  ]);

  if (workspacesQuery.isLoading) {
    return <PageState title="Loading Documents v8" variant="loading" />;
  }

  if (workspacesQuery.isError) {
    return (
      <PageState
        title="Unable to load workspaces"
        description="Refresh the page or try again later."
        variant="error"
      />
    );
  }

  return null;
}

export function DocumentsV8Workbench() {
  const session = useSession();
  const { workspace } = useWorkspaceContext();
  const currentUserLabel = session.user.display_name || session.user.email || "You";
  const model = useDocumentsV8Model({ currentUserLabel, workspaceId: workspace.id });

  return (
    <div className="documents-v8 flex min-h-screen flex-col bg-background text-foreground">
      <WorkbenchHeader
        search={model.state.search}
        onSearchChange={model.actions.setSearch}
        searchRef={model.refs.searchRef}
        viewMode={model.state.viewMode}
        onViewModeChange={model.actions.setViewMode}
        allViews={model.derived.allViews}
        activeViewId={model.state.activeViewId}
        onApplyView={model.actions.applyView}
        isSavingView={model.state.isSavingView}
        newViewName={model.state.newViewName}
        onStartSave={() => model.actions.setIsSavingView(true)}
        onCancelSave={model.actions.cancelSaveView}
        onNewViewNameChange={model.actions.setNewViewName}
        onSaveView={model.actions.saveView}
        onUploadClick={model.actions.handleUploadClick}
        fileInputRef={model.refs.fileInputRef}
        onFileInputChange={model.actions.handleFileInputChange}
      />

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <section className="flex min-h-0 flex-1 flex-col border-r border-border bg-background">
          <WorkbenchFilters
            statusFilter={model.state.statusFilter}
            statusCounts={model.derived.statusCounts}
            onStatusChange={model.actions.setStatusFilter}
            ownerFilter={model.state.ownerFilter}
            ownerOptions={model.derived.ownerOptions}
            onOwnerChange={model.actions.setOwnerFilter}
            tagOptions={model.derived.tagOptions}
            tagFilters={model.state.tagFilters}
            onToggleTag={model.actions.toggleTagFilter}
            onClearFilters={model.actions.clearFilters}
            hasActiveFilters={model.derived.hasActiveFilters}
            totalVisible={model.derived.sortedDocuments.length}
          />

          {model.derived.selectedCount > 0 ? (
            <WorkbenchBulkBar
              selectedCount={model.derived.selectedCount}
              onClear={model.actions.clearSelection}
              onAssign={model.actions.bulkAssign}
              onTag={model.actions.bulkTag}
              onRetry={model.actions.bulkRetry}
              onArchive={model.actions.bulkArchive}
            />
          ) : null}

          <div className="relative flex min-h-0 flex-1 flex-col">
            {model.state.viewMode === "grid" ? (
              <DocumentsGrid
                documents={model.derived.sortedDocuments}
                activeId={model.state.activeId}
                selectedIds={model.state.selectedIds}
                onSelect={model.actions.toggleSelect}
                onSelectAll={model.actions.selectAllVisible}
                onClearSelection={model.actions.clearSelection}
                allVisibleSelected={model.derived.allVisibleSelected}
                onActivate={model.actions.setActiveId}
                onDownload={model.actions.downloadDocument}
                onRetry={model.actions.retryDocument}
                onUploadClick={model.actions.handleUploadClick}
                onClearFilters={model.actions.clearFilters}
                showNoDocuments={model.derived.showNoDocuments}
                showNoResults={model.derived.showNoResults}
                isLoading={model.derived.isLoading}
                isError={model.derived.isError}
                hasNextPage={model.derived.hasNextPage}
                isFetchingNextPage={model.derived.isFetchingNextPage}
                onLoadMore={model.actions.loadMore}
                onRefresh={model.actions.refreshDocuments}
                now={model.derived.now}
                onKeyNavigate={model.actions.handleDocumentKeyDown}
                isDragging={model.state.isGridDragging}
                onDrop={model.actions.handleDropGrid}
                onDragOver={model.actions.handleGridDragOver}
                onDragLeave={model.actions.handleGridDragLeave}
              />
            ) : (
              <DocumentsBoard
                columns={model.derived.boardColumns}
                groupBy={model.state.groupBy}
                onGroupByChange={model.actions.setGroupBy}
                activeId={model.state.activeId}
                onActivate={model.actions.setActiveId}
                now={model.derived.now}
                activeDropColumn={model.state.activeDropColumn}
                onDropColumn={model.actions.handleDropColumn}
                onDragOverColumn={model.actions.handleDragOverColumn}
                onDragLeaveColumn={model.actions.handleDragLeaveColumn}
                onUploadToColumn={model.actions.handleUploadToColumn}
                canDragCards={model.derived.canDragCards}
                isLoading={model.derived.isLoading}
                isError={model.derived.isError}
                hasNextPage={model.derived.hasNextPage}
                isFetchingNextPage={model.derived.isFetchingNextPage}
                onLoadMore={model.actions.loadMore}
                onRefresh={model.actions.refreshDocuments}
              />
            )}
          </div>
        </section>

        <aside className="flex min-h-0 w-full flex-col bg-card lg:w-[38%]">
          <InspectorPanel
            document={model.derived.activeDocument}
            now={model.derived.now}
            activeSheetId={model.state.activeSheetId}
            onSheetChange={model.actions.setActiveSheetId}
            onDownload={model.actions.downloadDocument}
            onRetry={model.actions.retryDocument}
            onMoreActions={model.actions.handleMoreActions}
            onFixMapping={model.actions.handleFixMapping}
            activeRun={model.derived.activeRun}
            runLoading={model.derived.runLoading}
            outputUrl={model.derived.outputUrl}
            workbook={model.derived.workbook}
            workbookLoading={model.derived.workbookLoading}
            workbookError={model.derived.workbookError}
          />
        </aside>
      </div>
    </div>
  );
}

type WorkbenchModel = {
  state: {
    viewMode: ViewMode;
    groupBy: BoardGroup;
    search: string;
    statusFilter: StatusFilter;
    ownerFilter: string;
    tagFilters: string[];
    selectedIds: Set<string>;
    activeId: string | null;
    activeSheetId: string | null;
    savedViews: SavedView[];
    activeViewId: string;
    isSavingView: boolean;
    newViewName: string;
    isGridDragging: boolean;
    activeDropColumn: string | null;
  };
  derived: {
    now: number;
    tagOptions: string[];
    ownerOptions: string[];
    statusCounts: Record<StatusFilter, number>;
    sortedDocuments: DocumentEntry[];
    activeDocument: DocumentEntry | null;
    boardColumns: BoardColumn[];
    selectedCount: number;
    allVisibleSelected: boolean;
    showNoDocuments: boolean;
    showNoResults: boolean;
    allViews: SavedView[];
    hasActiveFilters: boolean;
    isLoading: boolean;
    isError: boolean;
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    activeRun: RunResource | null;
    runLoading: boolean;
    outputUrl: string | null;
    workbook: WorkbookPreview | null;
    workbookLoading: boolean;
    workbookError: boolean;
    canDragCards: boolean;
  };
  refs: {
    searchRef: MutableRefObject<HTMLInputElement | null>;
    fileInputRef: MutableRefObject<HTMLInputElement | null>;
  };
  actions: {
    setSearch: (value: string) => void;
    setViewMode: (value: ViewMode) => void;
    setGroupBy: (value: BoardGroup) => void;
    setStatusFilter: (value: StatusFilter) => void;
    setOwnerFilter: (value: string) => void;
    toggleTagFilter: (tag: string) => void;
    clearFilters: () => void;
    selectAllVisible: () => void;
    clearSelection: () => void;
    toggleSelect: (id: string) => void;
    setActiveId: (id: string) => void;
    setActiveSheetId: (id: string) => void;
    applyView: (id: string) => void;
    setIsSavingView: (value: boolean) => void;
    setNewViewName: (value: string) => void;
    cancelSaveView: () => void;
    saveView: () => void;
    handleUploadClick: () => void;
    handleFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
    downloadDocument: (doc: DocumentEntry | null) => void;
    retryDocument: (doc: DocumentEntry | null) => void;
    handleMoreActions: () => void;
    handleFixMapping: () => void;
    bulkAssign: () => void;
    bulkTag: () => void;
    bulkRetry: () => void;
    bulkArchive: () => void;
    refreshDocuments: () => void;
    loadMore: () => void;
    handleDropGrid: (event: DragEvent<HTMLDivElement>) => void;
    handleGridDragOver: (event: DragEvent<HTMLDivElement>) => void;
    handleGridDragLeave: () => void;
    handleDropColumn: (column: BoardColumn, event: DragEvent<HTMLDivElement>) => void;
    handleDragOverColumn: (columnId: string, event: DragEvent<HTMLDivElement>) => void;
    handleDragLeaveColumn: () => void;
    handleUploadToColumn: (context: UploadContext) => void;
    handleDocumentKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
  };
};

function useDocumentsV8Model({
  currentUserLabel,
  workspaceId,
}: {
  currentUserLabel: string;
  workspaceId: string;
}): WorkbenchModel {
  const { notifyToast } = useNotifications();
  const queryClient = useQueryClient();

  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [groupBy, setGroupBy] = useState<BoardGroup>("owner");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [ownerFilter, setOwnerFilter] = useState<string>(OWNER_FILTER_ALL);
  const [tagFilters, setTagFilters] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => readSavedViews());
  const [activeViewId, setActiveViewId] = useState("preset-all");
  const [isSavingView, setIsSavingView] = useState(false);
  const [newViewName, setNewViewName] = useState("");
  const [isGridDragging, setIsGridDragging] = useState(false);
  const [activeDropColumn, setActiveDropColumn] = useState<string | null>(null);

  const pendingUploadContextRef = useRef<UploadContext | null>(null);
  const uploadContextRef = useRef(new Map<string, UploadContext>());
  const uploadCreatedAtRef = useRef(new Map<string, number>());
  const handledUploadsRef = useRef(new Set<string>());
  const handledUploadFailuresRef = useRef(new Set<string>());
  const searchRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const presetViews = useMemo<SavedView[]>(
    () => [
      {
        id: "preset-all",
        name: "All work",
        filters: { search: "", status: "all", owner: OWNER_FILTER_ALL, tags: [] },
        view: "grid",
        groupBy: "owner",
      },
      {
        id: "preset-attention",
        name: "Needs attention",
        filters: { search: "", status: "attention", owner: OWNER_FILTER_ALL, tags: [] },
        view: "grid",
        groupBy: "status",
      },
      {
        id: "preset-ready",
        name: "Ready to deliver",
        filters: { search: "", status: "ready", owner: OWNER_FILTER_ALL, tags: [] },
        view: "grid",
        groupBy: "owner",
      },
      {
        id: "preset-mine",
        name: "Uploaded by me",
        filters: { search: "", status: "all", owner: currentUserLabel, tags: [] },
        view: "board",
        groupBy: "status",
      },
    ],
    [currentUserLabel],
  );

  const allViews = useMemo(() => [...presetViews, ...savedViews], [presetViews, savedViews]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    writeSavedViews(savedViews);
  }, [savedViews]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const startUpload = useCallback(
    (file: File, handlers: { onProgress: (progress: { loaded: number; total: number | null; percent: number | null }) => void }) =>
      uploadWorkspaceDocument(workspaceId, file, { onProgress: handlers.onProgress }),
    [workspaceId],
  );

  const uploadQueue = useUploadQueue<DocumentUploadResponse>({
    startUpload,
  });

  const sort = "-created_at";
  const documentsQuery = useInfiniteQuery<DocumentPage>({
    queryKey: documentsV8Keys.list(workspaceId, sort),
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
        const context = uploadContextRef.current.get(item.id);
        if (context?.tag) {
          patchDocumentTags(workspaceId, item.response.id, { add: [context.tag] }).catch((error) => {
            notifyToast({
              title: "Tag update failed",
              description: error instanceof Error ? error.message : "Unable to apply tags to the new document.",
              intent: "warning",
            });
          });
        }
        queryClient.invalidateQueries({ queryKey: documentsV8Keys.workspace(workspaceId) });
      }
      if (item.status === "failed" && item.error && !handledUploadFailuresRef.current.has(item.id)) {
        handledUploadFailuresRef.current.add(item.id);
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
      if (item.status === "succeeded" && item.response) {
        if (documentsById.has(item.response.id)) {
          return;
        }
        entries.push(buildDocumentEntry(item.response, { upload: item }));
        return;
      }
      const createdAt = uploadCreatedAtRef.current.get(item.id) ?? Date.now();
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
        if (documentsById.has(id)) {
          next.add(id);
        }
      });
      return next;
    });
  }, [documentsById]);

  useEffect(() => {
    if (documents.length === 0) {
      if (activeId !== null) {
        setActiveId(null);
      }
      return;
    }
    if (!activeId || !documentsByEntryId.has(activeId)) {
      setActiveId(documents[0]?.id ?? null);
    }
  }, [activeId, documents, documentsByEntryId]);

  const activeDocument = useMemo(
    () => (activeId ? documentsByEntryId.get(activeId) ?? null : null),
    [activeId, documentsByEntryId],
  );

  const activeRunId = activeDocument?.record?.last_run?.run_id ?? null;
  const runQuery = useQuery<RunResource | null>({
    queryKey: activeRunId ? documentsV8Keys.run(activeRunId) : [...documentsV8Keys.root(), "run", "none"],
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
    queryKey: outputUrl ? documentsV8Keys.workbook(outputUrl) : [...documentsV8Keys.root(), "workbook", "none"],
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

  const tagOptions = useMemo(() => {
    const tagSet = new Set<string>();
    documents.forEach((doc) => {
      doc.tags.forEach((tag) => tagSet.add(tag));
    });
    return Array.from(tagSet).sort((a, b) => a.localeCompare(b));
  }, [documents]);

  const ownerOptions = useMemo(() => {
    const ownerSet = new Set<string>();
    documents.forEach((doc) => {
      if (doc.owner) {
        ownerSet.add(doc.owner);
      }
    });
    return Array.from(ownerSet).sort((a, b) => a.localeCompare(b));
  }, [documents]);

  const baseFiltered = useMemo(() => {
    return documents.filter((doc) => {
      const matchesOwner =
        ownerFilter === OWNER_FILTER_ALL
          ? true
          : ownerFilter === OWNER_FILTER_UNASSIGNED
            ? !doc.owner
            : doc.owner === ownerFilter;
      if (!matchesOwner) {
        return false;
      }
      if (tagFilters.length > 0 && !tagFilters.every((tag) => doc.tags.includes(tag))) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      const haystack = [doc.name, doc.owner ?? "", doc.tags.join(" ")].join(" ").toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [documents, normalizedSearch, ownerFilter, tagFilters]);

  const statusCounts = useMemo(() => {
    const counts: Record<StatusFilter, number> = {
      all: baseFiltered.length,
      attention: 0,
      processing: 0,
      ready: 0,
      failed: 0,
      queued: 0,
      archived: 0,
    };
    baseFiltered.forEach((doc) => {
      if (doc.status === "processing") {
        counts.processing += 1;
      }
      if (doc.status === "ready") {
        counts.ready += 1;
      }
      if (doc.status === "failed") {
        counts.failed += 1;
      }
      if (doc.status === "queued") {
        counts.queued += 1;
      }
      if (doc.status === "archived") {
        counts.archived += 1;
      }
      if (isAttention(doc)) {
        counts.attention += 1;
      }
    });
    return counts;
  }, [baseFiltered]);

  const filteredDocuments = useMemo(() => {
    return baseFiltered.filter((doc) => {
      switch (statusFilter) {
        case "attention":
          return isAttention(doc);
        case "processing":
          return doc.status === "processing";
        case "ready":
          return doc.status === "ready";
        case "failed":
          return doc.status === "failed";
        case "queued":
          return doc.status === "queued";
        case "archived":
          return doc.status === "archived";
        default:
          return true;
      }
    });
  }, [baseFiltered, statusFilter]);

  const sortedDocuments = useMemo(() => {
    return [...filteredDocuments].sort((a, b) => b.createdAt - a.createdAt || a.name.localeCompare(b.name));
  }, [filteredDocuments]);

  const selectableIds = useMemo(
    () => sortedDocuments.filter((doc) => doc.record).map((doc) => doc.id),
    [sortedDocuments],
  );
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));
  const selectedCount = selectedIds.size;
  const showNoDocuments = documents.length === 0;
  const showNoResults = documents.length > 0 && sortedDocuments.length === 0;

  const hasActiveFilters = Boolean(
    search || statusFilter !== "all" || ownerFilter !== OWNER_FILTER_ALL || tagFilters.length > 0,
  );

  const boardColumns = useMemo<BoardColumn[]>(() => {
    if (groupBy === "status") {
      const statuses: DocumentStatus[] = ["queued", "processing", "ready", "failed", "archived"];
      return statuses.map((status) => ({
        id: status,
        label: STATUS_STYLES[status].label,
        context: { status },
        items: filteredDocuments.filter((doc) => doc.status === status),
      }));
    }

    if (groupBy === "tag") {
      if (tagOptions.length === 0) {
        return [
          {
            id: BOARD_UNTAGGED_ID,
            label: "Untagged",
            context: { tag: null },
            items: filteredDocuments.filter((doc) => doc.tags.length === 0),
          },
        ];
      }
      const columns = tagOptions.map((tag) => ({
        id: tag,
        label: tag,
        context: { tag },
        items: filteredDocuments.filter((doc) => doc.tags[0] === tag),
      }));
      columns.push({
        id: BOARD_UNTAGGED_ID,
        label: "Untagged",
        context: { tag: null },
        items: filteredDocuments.filter((doc) => doc.tags.length === 0),
      });
      return columns;
    }

    if (ownerOptions.length === 0) {
      return [
        {
          id: BOARD_UNASSIGNED_ID,
          label: "Unassigned",
          context: { owner: null },
          items: filteredDocuments.filter((doc) => !doc.owner),
        },
      ];
    }

    const columns = ownerOptions.map((owner) => ({
      id: owner,
      label: owner,
      context: { owner },
      items: filteredDocuments.filter((doc) => doc.owner === owner),
    }));
    columns.push({
      id: BOARD_UNASSIGNED_ID,
      label: "Unassigned",
      context: { owner: null },
      items: filteredDocuments.filter((doc) => !doc.owner),
    });
    return columns;
  }, [filteredDocuments, groupBy, ownerOptions, tagOptions]);

  const toggleTagFilter = useCallback((tag: string) => {
    setTagFilters((previous) => (previous.includes(tag) ? previous.filter((item) => item !== tag) : [...previous, tag]));
  }, []);

  const selectAllVisible = useCallback(() => {
    setSelectedIds(new Set(selectableIds));
  }, [selectableIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

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

  const applyView = useCallback(
    (viewId: string) => {
      const view = allViews.find((item) => item.id === viewId);
      if (!view) {
        return;
      }
      setActiveViewId(view.id);
      setSearch(view.filters.search);
      setStatusFilter(view.filters.status);
      setOwnerFilter(view.filters.owner);
      setTagFilters(view.filters.tags);
      setViewMode(view.view);
      setGroupBy(view.groupBy);
      setIsSavingView(false);
      setNewViewName("");
    },
    [allViews],
  );

  const saveView = useCallback(() => {
    const trimmed = newViewName.trim();
    if (!trimmed) {
      return;
    }
    const nextView: SavedView = {
      id: `view-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: trimmed,
      filters: {
        search,
        status: statusFilter,
        owner: ownerFilter,
        tags: tagFilters,
      },
      view: viewMode,
      groupBy,
    };
    setSavedViews((previous) => [...previous, nextView]);
    setActiveViewId(nextView.id);
    setIsSavingView(false);
    setNewViewName("");
    notifyToast({
      title: "View saved",
      description: `"${trimmed}" is ready for reuse.`,
      intent: "success",
    });
  }, [groupBy, newViewName, notifyToast, ownerFilter, search, statusFilter, tagFilters, viewMode]);

  const cancelSaveView = useCallback(() => {
    setIsSavingView(false);
    setNewViewName("");
  }, []);

  const clearFilters = useCallback(() => {
    setSearch("");
    setStatusFilter("all");
    setOwnerFilter(OWNER_FILTER_ALL);
    setTagFilters([]);
    setActiveViewId("preset-all");
  }, []);

  const handleFiles = useCallback(
    (files: FileList | null, context: UploadContext = {}) => {
      if (!files || files.length === 0) {
        return;
      }
      const nextItems = uploadQueue.enqueue(Array.from(files));
      const nowTimestamp = Date.now();
      nextItems.forEach((item, index) => {
        uploadContextRef.current.set(item.id, context);
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

  const openUploadDialog = useCallback((context?: UploadContext) => {
    pendingUploadContextRef.current = context ?? null;
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const context = pendingUploadContextRef.current ?? {};
      pendingUploadContextRef.current = null;
      handleFiles(event.target.files, context);
      event.target.value = "";
    },
    [handleFiles],
  );

  const handleUploadClick = useCallback(() => {
    openUploadDialog();
  }, [openUploadDialog]);

  const updateTags = useCallback(
    async (documentId: string, payload: { add?: readonly string[] | null; remove?: readonly string[] | null }) => {
      await patchDocumentTags(workspaceId, documentId, payload);
      queryClient.invalidateQueries({ queryKey: documentsV8Keys.workspace(workspaceId) });
    },
    [queryClient, workspaceId],
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

  const retryDocument = useCallback(
    (doc: DocumentEntry | null) => {
      if (!doc?.record || doc.status !== "failed") {
        return;
      }
      notifyToast({
        title: "Retry needs a configuration",
        description: "Select a configuration in the runs panel before reprocessing.",
        intent: "info",
      });
    },
    [notifyToast],
  );

  const handleMoreActions = useCallback(() => {
    notifyToast({
      title: "More actions coming soon",
      description: "Bulk exports, sharing, and automated delivery are on the way.",
      intent: "info",
    });
  }, [notifyToast]);

  const handleFixMapping = useCallback(() => {
    notifyToast({
      title: "Mapping editor coming soon",
      description: "We are polishing the mapping workflow for v8.",
      intent: "info",
    });
  }, [notifyToast]);

  const bulkAssign = useCallback(() => {
    notifyToast({
      title: "Assignment is read-only",
      description: "Uploader is derived from the original upload and cannot be reassigned yet.",
      intent: "info",
    });
  }, [notifyToast]);

  const bulkTag = useCallback(() => {
    if (selectedIds.size === 0) {
      return;
    }
    const targets = Array.from(selectedIds);
    void client.POST("/api/v1/workspaces/{workspace_id}/documents/batch/tags", {
      params: { path: { workspace_id: workspaceId } },
      body: { document_ids: targets, add: ["priority"] },
    })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: documentsV8Keys.workspace(workspaceId) });
        notifyToast({
          title: "Tags updated",
          description: `${targets.length} document${targets.length === 1 ? "" : "s"} tagged priority.`,
          intent: "success",
        });
      })
      .catch((error) => {
        notifyToast({
          title: "Unable to update tags",
          description: error instanceof Error ? error.message : "Tagging failed.",
          intent: "warning",
        });
      });
  }, [notifyToast, queryClient, selectedIds, workspaceId]);

  const bulkRetry = useCallback(() => {
    notifyToast({
      title: "Retry requires a configuration",
      description: "Open the runs panel to select a configuration before retrying.",
      intent: "info",
    });
  }, [notifyToast]);

  const bulkArchive = useCallback(() => {
    if (selectedIds.size === 0) {
      return;
    }
    const ids = Array.from(selectedIds);
    void client.POST("/api/v1/workspaces/{workspace_id}/documents/batch/delete", {
      params: { path: { workspace_id: workspaceId } },
      body: { document_ids: ids },
    })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: documentsV8Keys.workspace(workspaceId) });
        setSelectedIds(new Set());
        notifyToast({
          title: "Archived",
          description: `${ids.length} document${ids.length === 1 ? "" : "s"} archived.`,
          intent: "info",
        });
      })
      .catch((error) => {
        notifyToast({
          title: "Archive failed",
          description: error instanceof Error ? error.message : "Unable to archive documents.",
          intent: "warning",
        });
      });
  }, [notifyToast, queryClient, selectedIds, workspaceId]);

  const handleDropGrid = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsGridDragging(false);
      if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
        handleFiles(event.dataTransfer.files);
      }
    },
    [handleFiles],
  );

  const handleGridDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (!event.dataTransfer.types.includes("Files")) {
      return;
    }
    event.preventDefault();
    setIsGridDragging(true);
  }, []);

  const handleGridDragLeave = useCallback(() => {
    setIsGridDragging(false);
  }, []);

  const handleDropColumn = useCallback(
    (column: BoardColumn, event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setActiveDropColumn(null);
      if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
        const context = column.context.tag ? { tag: column.context.tag } : {};
        handleFiles(event.dataTransfer.files, context);
        return;
      }
      const docId = event.dataTransfer.getData("text/plain");
      if (!docId) {
        return;
      }
      const entry = documentsByEntryId.get(docId);
      if (!entry?.record) {
        return;
      }
      if (groupBy !== "tag") {
        notifyToast({
          title: "Columns are read-only",
          description: "Status and uploader are managed by the system.",
          intent: "info",
        });
        return;
      }
      const tag = column.context.tag ?? null;
      if (tag) {
        void updateTags(entry.record.id, { add: [tag] });
      } else if (entry.tags.length > 0) {
        void updateTags(entry.record.id, { remove: entry.tags });
      }
    },
    [documentsByEntryId, groupBy, handleFiles, notifyToast, updateTags],
  );

  const handleDragOverColumn = useCallback((columnId: string, event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setActiveDropColumn(columnId);
  }, []);

  const handleDragLeaveColumn = useCallback(() => {
    setActiveDropColumn(null);
  }, []);

  const handleUploadToColumn = useCallback(
    (context: UploadContext) => {
      if (context.owner || context.status) {
        notifyToast({
          title: "Uploads inherit tags only",
          description: "Uploader and status are set automatically by the system.",
          intent: "info",
        });
      }
      openUploadDialog(context.tag ? { tag: context.tag } : undefined);
    },
    [notifyToast, openUploadDialog],
  );

  const handleDocumentKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (sortedDocuments.length === 0) {
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
        return;
      }
      event.preventDefault();
      const currentIndex = sortedDocuments.findIndex((doc) => doc.id === activeId);
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

  const setActiveIdValue = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const setActiveSheetIdValue = useCallback((id: string) => {
    setActiveSheetId(id);
  }, []);

  const loadMore = useCallback(() => {
    if (documentsQuery.hasNextPage) {
      void documentsQuery.fetchNextPage();
    }
  }, [documentsQuery]);

  const refreshDocuments = useCallback(() => {
    void documentsQuery.refetch();
  }, [documentsQuery]);

  return {
    state: {
      viewMode,
      groupBy,
      search,
      statusFilter,
      ownerFilter,
      tagFilters,
      selectedIds,
      activeId,
      activeSheetId,
      savedViews,
      activeViewId,
      isSavingView,
      newViewName,
      isGridDragging,
      activeDropColumn,
    },
    derived: {
      now,
      tagOptions,
      ownerOptions,
      statusCounts,
      sortedDocuments,
      activeDocument,
      boardColumns,
      selectedCount,
      allVisibleSelected,
      showNoDocuments,
      showNoResults,
      allViews,
      hasActiveFilters,
      isLoading: documentsQuery.isLoading,
      isError: documentsQuery.isError,
      hasNextPage: Boolean(documentsQuery.hasNextPage),
      isFetchingNextPage: documentsQuery.isFetchingNextPage,
      activeRun: runQuery.data ?? null,
      runLoading: runQuery.isFetching,
      outputUrl,
      workbook: workbookQuery.data ?? null,
      workbookLoading: workbookQuery.isLoading,
      workbookError: workbookQuery.isError,
      canDragCards: groupBy === "tag",
    },
    refs: {
      searchRef,
      fileInputRef,
    },
    actions: {
      setSearch,
      setViewMode,
      setGroupBy,
      setStatusFilter,
      setOwnerFilter,
      toggleTagFilter,
      clearFilters,
      selectAllVisible,
      clearSelection,
      toggleSelect,
      setActiveId: setActiveIdValue,
      setActiveSheetId: setActiveSheetIdValue,
      applyView,
      setIsSavingView,
      setNewViewName,
      cancelSaveView,
      saveView,
      handleUploadClick,
      handleFileInputChange,
      downloadDocument,
      retryDocument,
      handleMoreActions,
      handleFixMapping,
      bulkAssign,
      bulkTag,
      bulkRetry,
      bulkArchive,
      refreshDocuments,
      loadMore,
      handleDropGrid,
      handleGridDragOver,
      handleGridDragLeave,
      handleDropColumn,
      handleDragOverColumn,
      handleDragLeaveColumn,
      handleUploadToColumn,
      handleDocumentKeyDown,
    },
  };
}

function WorkbenchHeader({
  search,
  onSearchChange,
  searchRef,
  viewMode,
  onViewModeChange,
  allViews,
  activeViewId,
  onApplyView,
  isSavingView,
  newViewName,
  onStartSave,
  onCancelSave,
  onNewViewNameChange,
  onSaveView,
  onUploadClick,
  fileInputRef,
  onFileInputChange,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchRef: MutableRefObject<HTMLInputElement | null>;
  viewMode: ViewMode;
  onViewModeChange: (value: ViewMode) => void;
  allViews: SavedView[];
  activeViewId: string;
  onApplyView: (id: string) => void;
  isSavingView: boolean;
  newViewName: string;
  onStartSave: () => void;
  onCancelSave: () => void;
  onNewViewNameChange: (value: string) => void;
  onSaveView: () => void;
  onUploadClick: () => void;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  onFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <header className="border-b border-border bg-card">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-muted text-foreground">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-foreground">Documents</h1>
            <p className="text-xs text-muted-foreground">Work items for normalization and delivery</p>
          </div>
        </div>

        <div className="flex min-w-[240px] flex-1 items-center">
          <label className="sr-only" htmlFor="documents-v8-search">
            Search documents
          </label>
          <div className="relative w-full">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              <SearchIcon className="h-4 w-4" />
            </span>
            <Input
              id="documents-v8-search"
              ref={searchRef}
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search by name, uploader, or tag"
              className="pl-9"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center rounded-lg border border-border bg-background p-1 text-xs shadow-sm">
            <Button
              type="button"
              size="sm"
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("grid")}
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "grid" ? "shadow-sm" : "text-muted-foreground")}
              aria-pressed={viewMode === "grid"}
              aria-label="Grid view"
            >
              <GridIcon className="h-4 w-4" />
              Grid
            </Button>
            <Button
              type="button"
              size="sm"
              variant={viewMode === "board" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("board")}
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "board" ? "shadow-sm" : "text-muted-foreground")}
              aria-pressed={viewMode === "board"}
              aria-label="Board view"
            >
              <BoardIcon className="h-4 w-4" />
              Board
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="documents-v8-view-select">
              Saved view
            </label>
            <Select
              id="documents-v8-view-select"
              value={activeViewId}
              onChange={(event) => onApplyView(event.target.value)}
              className="min-w-[11rem] text-xs"
            >
              {allViews.map((view) => (
                <option key={view.id} value={view.id}>
                  {view.name}
                </option>
              ))}
            </Select>

            {isSavingView ? (
              <div className="flex items-center gap-2">
                <Input
                  value={newViewName}
                  onChange={(event) => onNewViewNameChange(event.target.value)}
                  placeholder="Name this view"
                  className="w-40 text-xs"
                />
                <Button type="button" onClick={onSaveView} size="sm" className="text-xs">
                  Save
                </Button>
                <Button type="button" onClick={onCancelSave} size="sm" variant="ghost" className="text-xs">
                  Cancel
                </Button>
              </div>
            ) : (
              <Button type="button" onClick={onStartSave} size="sm" variant="secondary" className="text-xs">
                Save view
              </Button>
            )}
          </div>

          <Button type="button" onClick={onUploadClick} size="md" className="gap-2">
            <UploadIcon className="h-4 w-4" />
            Upload
          </Button>
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onFileInputChange} />
        </div>
      </div>
    </header>
  );
}

function WorkbenchFilters({
  statusFilter,
  statusCounts,
  onStatusChange,
  ownerFilter,
  ownerOptions,
  onOwnerChange,
  tagOptions,
  tagFilters,
  onToggleTag,
  onClearFilters,
  hasActiveFilters,
  totalVisible,
}: {
  statusFilter: StatusFilter;
  statusCounts: Record<StatusFilter, number>;
  onStatusChange: (value: StatusFilter) => void;
  ownerFilter: string;
  ownerOptions: string[];
  onOwnerChange: (value: string) => void;
  tagOptions: string[];
  tagFilters: string[];
  onToggleTag: (tag: string) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
  totalVisible: number;
}) {
  return (
    <div className="border-b border-border bg-card px-6 py-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Work queue</p>
          <p className="text-sm font-semibold text-foreground">{totalVisible} documents in view</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.id}
              type="button"
              onClick={() => onStatusChange(filter.id)}
              className={clsx(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                statusFilter === filter.id
                  ? "border-brand-300 bg-brand-50 text-brand-700"
                  : "border-transparent bg-muted text-muted-foreground hover:text-foreground",
              )}
              aria-pressed={statusFilter === filter.id}
            >
              {filter.label}
              <span className="text-[11px] text-muted-foreground">{numberFormatter.format(statusCounts[filter.id])}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-muted-foreground">Uploader</span>
          <Select value={ownerFilter} onChange={(event) => onOwnerChange(event.target.value)} className="w-40 text-xs">
            <option value={OWNER_FILTER_ALL}>All uploaders</option>
            {ownerOptions.map((owner) => (
              <option key={owner} value={owner}>
                {owner}
              </option>
            ))}
            <option value={OWNER_FILTER_UNASSIGNED}>Unassigned</option>
          </Select>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-muted-foreground">Tags</span>
          {tagOptions.length === 0 ? (
            <span className="text-xs text-muted-foreground">No tags yet</span>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {tagOptions.map((tag) => {
                const isSelected = tagFilters.includes(tag);
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => onToggleTag(tag)}
                    className={clsx(
                      "rounded-full border px-3 py-1 text-xs font-semibold transition",
                      isSelected
                        ? "border-brand-300 bg-brand-50 text-brand-700"
                        : "border-transparent bg-muted text-muted-foreground hover:text-foreground",
                    )}
                    aria-pressed={isSelected}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {hasActiveFilters ? (
          <button type="button" onClick={onClearFilters} className="text-xs font-semibold text-brand-600">
            Clear filters
          </button>
        ) : null}
      </div>
    </div>
  );
}

function WorkbenchBulkBar({
  selectedCount,
  onClear,
  onAssign,
  onTag,
  onRetry,
  onArchive,
}: {
  selectedCount: number;
  onClear: () => void;
  onAssign: () => void;
  onTag: () => void;
  onRetry: () => void;
  onArchive: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card/80 px-6 py-3 text-xs">
      <div className="flex items-center gap-2 font-semibold text-foreground">
        <span>{selectedCount} selected</span>
        <button type="button" onClick={onClear} className="text-muted-foreground">
          Clear
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" onClick={onAssign} size="sm" variant="secondary" className="rounded-full text-xs">
          Assign to me
        </Button>
        <Button type="button" onClick={onTag} size="sm" variant="secondary" className="rounded-full text-xs">
          Tag priority
        </Button>
        <Button type="button" onClick={onRetry} size="sm" variant="secondary" className="rounded-full text-xs">
          Retry
        </Button>
        <Button type="button" onClick={onArchive} size="sm" variant="secondary" className="rounded-full text-xs">
          Archive
        </Button>
      </div>
    </div>
  );
}

function DocumentsGrid({
  documents,
  activeId,
  selectedIds,
  onSelect,
  onSelectAll,
  onClearSelection,
  allVisibleSelected,
  onActivate,
  onDownload,
  onRetry,
  onUploadClick,
  onClearFilters,
  showNoDocuments,
  showNoResults,
  isLoading,
  isError,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
  onRefresh,
  now,
  onKeyNavigate,
  isDragging,
  onDrop,
  onDragOver,
  onDragLeave,
}: {
  documents: DocumentEntry[];
  activeId: string | null;
  selectedIds: Set<string>;
  onSelect: (id: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  allVisibleSelected: boolean;
  onActivate: (id: string) => void;
  onDownload: (doc: DocumentEntry | null) => void;
  onRetry: (doc: DocumentEntry | null) => void;
  onUploadClick: () => void;
  onClearFilters: () => void;
  showNoDocuments: boolean;
  showNoResults: boolean;
  isLoading: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
  onRefresh: () => void;
  now: number;
  onKeyNavigate: (event: KeyboardEvent<HTMLDivElement>) => void;
  isDragging: boolean;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeave: () => void;
}) {
  const hasSelectable = documents.some((doc) => doc.record);
  const showLoading = isLoading && documents.length === 0;
  const showError = isError && documents.length === 0;

  return (
    <div
      className="relative flex min-h-0 flex-1 flex-col"
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      aria-label="Document list drop zone"
    >
      {isDragging ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-card/70 backdrop-blur-sm">
          <div className="rounded-2xl border border-dashed border-brand-400 bg-card px-6 py-4 text-sm font-semibold text-brand-700 shadow-sm">
            Drop files to upload into this workspace
          </div>
        </div>
      ) : null}

      <div className="hidden border-b border-border bg-card px-6 py-2 text-xs uppercase tracking-[0.18em] text-muted-foreground md:grid md:grid-cols-[auto_minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,0.6fr)]">
        <div>
          <input
            type="checkbox"
            checked={allVisibleSelected}
            onChange={(event) => (event.target.checked ? onSelectAll() : onClearSelection())}
            aria-label="Select all visible documents"
            disabled={!hasSelectable}
          />
        </div>
        <div>Document</div>
        <div>Status</div>
        <div>Uploader</div>
        <div>Tags</div>
        <div className="text-right">Updated</div>
      </div>

      <div
        className="flex-1 overflow-y-auto px-6 py-3"
        onKeyDown={onKeyNavigate}
        tabIndex={0}
        role="list"
        aria-label="Document list"
      >
        {showLoading ? (
          <EmptyState title="Loading documents" description="Fetching the latest processing activity." />
        ) : showError ? (
          <EmptyState
            title="Unable to load documents"
            description="We could not refresh this view. Try again."
            action={{ label: "Try again", onClick: onRefresh }}
          />
        ) : showNoDocuments ? (
          <EmptyState
            title="No documents yet"
            description="Upload your first batch to start the processing loop."
            action={{ label: "Upload files", onClick: onUploadClick }}
          />
        ) : showNoResults ? (
          <EmptyState
            title="No results in this view"
            description="Try clearing filters or adjusting the search."
            action={{ label: "Clear filters", onClick: onClearFilters }}
          />
        ) : (
          <div className="flex flex-col gap-2">
            {documents.map((doc) => {
              const isSelectable = Boolean(doc.record);
              return (
                <div
                  key={doc.id}
                  role="listitem"
                  tabIndex={0}
                  onClick={() => onActivate(doc.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onActivate(doc.id);
                    }
                  }}
                  className={clsx(
                    "group flex flex-col gap-3 rounded-2xl border bg-card px-4 py-3 shadow-sm transition md:grid md:grid-cols-[auto_minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,0.6fr)] md:items-center",
                    activeId === doc.id ? "border-brand-400" : "border-border hover:border-brand-300",
                  )}
                >
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(doc.id)}
                      onChange={() => {
                        if (isSelectable) {
                          onSelect(doc.id);
                        }
                      }}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Select ${doc.name}`}
                      disabled={!isSelectable}
                    />
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border bg-background">
                      <DocumentIcon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{doc.name}</p>
                      <p className="text-xs text-muted-foreground">Uploaded {formatRelativeTime(now, doc.createdAt)}</p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <StatusPill status={doc.status} />
                    {doc.status === "processing" && doc.progress !== undefined ? (
                      <span className="text-[11px] text-muted-foreground">
                        {doc.progress ?? 0}% - {doc.stage ?? "Processing"}
                      </span>
                    ) : null}
                    {doc.status === "processing" && doc.progress === undefined && doc.stage ? (
                      <span className="text-[11px] text-muted-foreground">{doc.stage}</span>
                    ) : null}
                    <MappingBadge mapping={doc.mapping} />
                  </div>

                  <div className="text-xs font-semibold text-muted-foreground">{doc.owner ?? "Unassigned"}</div>

                  <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                    {doc.tags.length === 0 ? (
                      <span className="text-[11px]">No tags</span>
                    ) : (
                      <>
                        {doc.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold"
                          >
                            {tag}
                          </span>
                        ))}
                        {doc.tags.length > 2 ? (
                          <span className="text-[11px] text-muted-foreground">+{doc.tags.length - 2}</span>
                        ) : null}
                      </>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-xs text-muted-foreground md:justify-end">
                    <span>{formatRelativeTime(now, doc.updatedAt)}</span>
                    <div className="flex items-center gap-2 opacity-0 transition group-hover:opacity-100">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 rounded-full p-0"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDownload(doc);
                        }}
                        aria-label={`Download ${doc.name}`}
                        disabled={!doc.record || doc.status !== "ready"}
                      >
                        <DownloadIcon className="h-3 w-3" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 rounded-full p-0"
                        onClick={(event) => {
                          event.stopPropagation();
                          onRetry(doc);
                        }}
                        aria-label={`Retry ${doc.name}`}
                        disabled={!doc.record || doc.status !== "failed"}
                      >
                        <RetryIcon className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
            {hasNextPage ? (
              <div className="flex justify-center pt-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="text-xs"
                  onClick={onLoadMore}
                  disabled={isFetchingNextPage}
                >
                  {isFetchingNextPage ? "Loading more..." : "Load more"}
                </Button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

function DocumentsBoard({
  columns,
  groupBy,
  onGroupByChange,
  activeId,
  onActivate,
  now,
  activeDropColumn,
  onDropColumn,
  onDragOverColumn,
  onDragLeaveColumn,
  onUploadToColumn,
  canDragCards,
  isLoading,
  isError,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
  onRefresh,
}: {
  columns: BoardColumn[];
  groupBy: BoardGroup;
  onGroupByChange: (value: BoardGroup) => void;
  activeId: string | null;
  onActivate: (id: string) => void;
  now: number;
  activeDropColumn: string | null;
  onDropColumn: (column: BoardColumn, event: DragEvent<HTMLDivElement>) => void;
  onDragOverColumn: (columnId: string, event: DragEvent<HTMLDivElement>) => void;
  onDragLeaveColumn: () => void;
  onUploadToColumn: (context: UploadContext) => void;
  canDragCards: boolean;
  isLoading: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
  onRefresh: () => void;
}) {
  const totalItems = columns.reduce((sum, column) => sum + column.items.length, 0);
  const showLoading = isLoading && totalItems === 0;
  const showError = isError && totalItems === 0;
  const helperText = canDragCards
    ? "Drag cards to retag or drop files into a column."
    : "Drop files into a column to upload. Card drag is disabled.";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-6 py-3 text-xs">
        <div className="flex items-center gap-2 font-semibold text-muted-foreground">
          <span>Group by</span>
          <div className="flex items-center rounded-full border border-border bg-background px-1 py-1">
            {BOARD_GROUPS.map((group) => (
              <button
                key={group.id}
                type="button"
                onClick={() => onGroupByChange(group.id)}
                className={clsx(
                  "rounded-full px-3 py-1 text-xs font-semibold transition",
                  groupBy === group.id ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={groupBy === group.id}
              >
                {group.label}
              </button>
            ))}
          </div>
        </div>
        <span className="text-muted-foreground">{helperText}</span>
      </div>

      <div className="flex-1 overflow-x-auto px-6 py-4">
        {showLoading ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-border bg-card text-sm text-muted-foreground">
            Loading board columns...
          </div>
        ) : showError ? (
          <EmptyState
            title="Unable to load documents"
            description="We could not refresh this board. Try again."
            action={{ label: "Try again", onClick: onRefresh }}
          />
        ) : (
          <div className="flex min-h-full gap-4">
            {columns.map((column) => (
              <div key={column.id} className="flex w-72 min-w-[18rem] flex-col">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {groupBy === "status" ? (
                      <span
                        className={clsx("h-2.5 w-2.5 rounded-full", STATUS_STYLES[column.id as DocumentStatus].dot)}
                        aria-hidden
                      />
                    ) : groupBy === "owner" ? (
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-foreground">
                        {column.label === "Unassigned" ? "?" : getInitials(column.label)}
                      </span>
                    ) : (
                      <TagIcon className="h-4 w-4 text-muted-foreground" />
                    )}
                    <div>
                      <p className="text-sm font-semibold text-foreground">{column.label}</p>
                      <p className="text-xs text-muted-foreground">{column.items.length} items</p>
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 rounded-full px-2 text-[11px]"
                    aria-label={`Upload directly to ${column.label}`}
                    onClick={() => onUploadToColumn(column.context)}
                  >
                    + Upload
                  </Button>
                </div>

                <div
                  className={clsx(
                    "flex min-h-[12rem] flex-1 flex-col gap-3 rounded-2xl border border-dashed px-3 py-3 transition",
                    activeDropColumn === column.id ? "border-brand-400 bg-brand-50" : "border-border bg-card",
                  )}
                  onDragOver={(event) => onDragOverColumn(column.id, event)}
                  onDragLeave={onDragLeaveColumn}
                  onDrop={(event) => onDropColumn(column, event)}
                  aria-label={`Board column ${column.label}`}
                >
                  {column.items.length === 0 ? (
                    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-xs text-muted-foreground">
                      <p>No items yet</p>
                      <p>Drop files here to upload</p>
                    </div>
                  ) : (
                    column.items.map((doc) => {
                      const isDraggable = canDragCards && Boolean(doc.record);
                      return (
                        <div
                          key={doc.id}
                          draggable={isDraggable}
                          onDragStart={(event) => {
                            if (!isDraggable) {
                              event.preventDefault();
                              return;
                            }
                            event.dataTransfer.setData("text/plain", doc.id);
                            event.dataTransfer.effectAllowed = "move";
                          }}
                          onClick={() => onActivate(doc.id)}
                          className={clsx(
                            "flex flex-col gap-3 rounded-2xl border bg-card px-3 py-3 shadow-sm transition",
                            activeId === doc.id ? "border-brand-400" : "border-border hover:border-brand-300",
                            !isDraggable && "cursor-default",
                          )}
                          role="button"
                          aria-label={`Open ${doc.name}`}
                          aria-disabled={!isDraggable}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className="text-sm font-semibold text-foreground">{doc.name}</p>
                              <p className="text-xs text-muted-foreground">Updated {formatRelativeTime(now, doc.updatedAt)}</p>
                            </div>
                            <span className={clsx("h-2.5 w-2.5 rounded-full", STATUS_STYLES[doc.status].dot)} aria-hidden />
                          </div>
                          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                            <span className="font-semibold">{doc.owner ?? "Unassigned"}</span>
                            {doc.tags.length > 0 ? (
                              <span className="rounded-full border border-border bg-background px-2 py-0.5">
                                {doc.tags[0]}
                                {doc.tags.length > 1 ? ` +${doc.tags.length - 1}` : ""}
                              </span>
                            ) : null}
                            {isAttention(doc) ? (
                              <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-700">
                                Needs mapping
                              </span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {hasNextPage ? (
        <div className="flex justify-center border-t border-border bg-card px-6 py-3">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="text-xs"
            onClick={onLoadMore}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function InspectorPanel({
  document,
  now,
  activeSheetId,
  onSheetChange,
  onDownload,
  onRetry,
  onMoreActions,
  onFixMapping,
  activeRun,
  runLoading,
  outputUrl,
  workbook,
  workbookLoading,
  workbookError,
}: {
  document: DocumentEntry | null;
  now: number;
  activeSheetId: string | null;
  onSheetChange: (id: string) => void;
  onDownload: (doc: DocumentEntry | null) => void;
  onRetry: (doc: DocumentEntry | null) => void;
  onMoreActions: () => void;
  onFixMapping: () => void;
  activeRun: RunResource | null;
  runLoading: boolean;
  outputUrl: string | null;
  workbook: WorkbookPreview | null;
  workbookLoading: boolean;
  workbookError: boolean;
}) {
  const sheets = workbook?.sheets ?? [];
  const selectedSheetId = activeSheetId ?? sheets[0]?.name ?? "";
  const activeSheet = sheets.find((sheet) => sheet.name === selectedSheetId) ?? sheets[0];
  const canDownload = Boolean(document?.record && document.status === "ready" && outputUrl);
  const outputMeta = activeRun?.output;
  const outputFilename = document ? outputMeta?.filename ?? buildNormalizedFilename(document.name) : "";
  const outputSize =
    outputMeta?.size_bytes && outputMeta.size_bytes > 0 ? formatBytes(outputMeta.size_bytes) : null;
  const outputSheetSummary = activeSheet
    ? `${numberFormatter.format(activeSheet.totalRows)} rows · ${numberFormatter.format(activeSheet.totalColumns)} cols`
    : null;
  const outputSummary = [outputSize, outputSheetSummary].filter(Boolean).join(" · ");
  const isUploading = Boolean(document?.upload && document.upload.status === "uploading");

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Preview</p>
          <h2 className="truncate text-lg font-semibold text-foreground">
            {document ? document.name : "Select a document"}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {document ? (
              <>
                <StatusPill status={document.status} />
                <span>{getStatusDescription(document, activeRun)}</span>
              </>
            ) : (
              <span>Choose a file to inspect the processed output.</span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            className="gap-2 text-xs"
            onClick={() => onDownload(document)}
            disabled={!canDownload}
            aria-label="Download processed XLSX"
          >
            <DownloadIcon className="h-4 w-4" />
            Download processed XLSX
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="text-xs"
            onClick={() => onRetry(document)}
            disabled={!document || document.status !== "failed"}
          >
            Retry
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-xs"
            aria-label="More actions"
            onClick={onMoreActions}
          >
            More
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {!document ? (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-background px-6 text-center text-sm text-muted-foreground">
            <p className="text-sm font-semibold text-foreground">Preview is ready when you are.</p>
            <p>Select a document from the left to inspect its processed output.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Summary</h3>
                <span className="text-xs text-muted-foreground">Updated {formatRelativeTime(now, document.updatedAt)}</span>
              </div>
              <dl className="mt-4 grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Uploader</dt>
                  <dd className="font-semibold text-foreground">{document.owner ?? "Unassigned"}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Tags</dt>
                  <dd className="flex flex-wrap items-center justify-end gap-2 text-xs">
                    {document.tags.length === 0 ? (
                      <span className="text-muted-foreground">No tags</span>
                    ) : (
                      document.tags.map((tag) => (
                        <span key={tag} className="rounded-full border border-border bg-background px-2 py-0.5 font-semibold">
                          {tag}
                        </span>
                      ))
                    )}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Mapping health</dt>
                  <dd className="text-right text-xs font-semibold text-foreground">
                    {getMappingHealthLabel(document.mapping)}
                  </dd>
                </div>
                {document.status === "processing" && document.progress !== undefined ? (
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted-foreground">Progress</dt>
                    <dd className="text-xs font-semibold text-foreground">
                      {document.progress ?? 0}% - {document.stage ?? "Processing"}
                    </dd>
                  </div>
                ) : null}
                {document.status === "processing" && document.progress === undefined && document.stage ? (
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted-foreground">Stage</dt>
                    <dd className="text-xs font-semibold text-foreground">{document.stage}</dd>
                  </div>
                ) : null}
              </dl>
            </section>

            <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Processed output</h3>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 rounded-full px-3 text-[11px]"
                  disabled
                  onClick={onFixMapping}
                  aria-label="Fix mapping (coming soon)"
                  title="Coming soon"
                >
                  Fix mapping
                </Button>
              </div>

              {document.status === "ready" ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground">{outputFilename}</span>
                  {outputSummary ? <span>{outputSummary}</span> : null}
                </div>
              ) : null}

              <div className="mt-4 rounded-2xl border border-border bg-background">
                {document.status === "ready" ? (
                  !outputUrl ? (
                    <div className="flex flex-col gap-2 px-4 py-6 text-sm text-muted-foreground">
                      <p className="font-semibold text-foreground">Output link unavailable</p>
                      <p>We could not load the processed output link yet. Try again in a moment.</p>
                    </div>
                  ) : workbookLoading ? (
                    <div className="flex flex-col gap-2 px-4 py-6 text-sm text-muted-foreground">
                      <p className="font-semibold text-foreground">Loading preview</p>
                      <p>Fetching the processed workbook for review.</p>
                    </div>
                  ) : workbookError ? (
                    <div className="flex flex-col gap-2 px-4 py-6 text-sm text-muted-foreground">
                      <p className="font-semibold text-foreground">Preview unavailable</p>
                      <p>The XLSX is ready to download, but we could not render the preview.</p>
                    </div>
                  ) : activeSheet ? (
                    <div>
                      <TabsRoot value={selectedSheetId} onValueChange={onSheetChange}>
                        <TabsList className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-xs">
                          {sheets.map((sheet) => (
                            <TabsTrigger
                              key={sheet.name}
                              value={sheet.name}
                              className={clsx(
                                "rounded-full px-3 py-1 font-semibold transition",
                                selectedSheetId === sheet.name
                                  ? "bg-card text-foreground shadow-sm"
                                  : "text-muted-foreground hover:text-foreground",
                              )}
                            >
                              {sheet.name}
                            </TabsTrigger>
                          ))}
                        </TabsList>
                        {sheets.map((sheet) => (
                          <TabsContent key={sheet.name} value={sheet.name} className="max-h-72 overflow-auto">
                            <PreviewTable sheet={sheet} />
                          </TabsContent>
                        ))}
                      </TabsRoot>
                      {(activeSheet.truncatedRows || activeSheet.truncatedColumns) && (
                        <div className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
                          Showing first {Math.min(activeSheet.totalRows, MAX_PREVIEW_ROWS)} rows and{" "}
                          {Math.min(activeSheet.totalColumns, MAX_PREVIEW_COLUMNS)} columns.
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2 px-4 py-6 text-sm text-muted-foreground">
                      <p className="font-semibold text-foreground">Preview unavailable for this output</p>
                      <p>The processed XLSX is ready to download, but we cannot render a preview here.</p>
                    </div>
                  )
                ) : document.status === "failed" ? (
                  <div className="flex flex-col gap-3 px-4 py-6 text-sm text-muted-foreground">
                    <p className="font-semibold text-rose-600">{document.error?.summary ?? "Processing failed"}</p>
                    <p>{document.error?.detail ?? "We could not complete normalization for this file."}</p>
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" size="sm" variant="danger" className="text-xs" onClick={() => onRetry(document)}>
                        Retry now
                      </Button>
                      <Button type="button" size="sm" variant="secondary" className="text-xs" disabled onClick={onFixMapping}>
                        Fix mapping (soon)
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">{document.error?.nextStep ?? "Retry now or fix mapping later."}</p>
                  </div>
                ) : document.status === "archived" ? (
                  <div className="flex flex-col gap-2 px-4 py-6 text-sm text-muted-foreground">
                    <p className="font-semibold text-foreground">Archived</p>
                    <p>This document is archived and no longer in the active workflow.</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-3 px-4 py-6 text-sm text-muted-foreground">
                    <p className="font-semibold text-foreground">
                      {isUploading
                        ? "Uploading to workspace"
                        : document.status === "processing"
                          ? "Processing output"
                          : "Queued for processing"}
                    </p>
                    <p>
                      {document.stage ?? (isUploading ? "Uploading file" : "Preparing normalized output")}
                    </p>
                    {document.progress !== undefined ? (
                      <div className="h-2 overflow-hidden rounded-full bg-card">
                        <div
                          className="h-full bg-gradient-to-r from-brand-200 via-brand-500 to-brand-200"
                          style={{ width: `${document.progress}%` }}
                        />
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm">
              <h3 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">History</h3>
              <div className="mt-4 flex flex-col gap-3 text-xs text-muted-foreground">
                {document.history.length > 0 ? (
                  document.history.map((event) => (
                    <div key={event.id} className="flex items-start gap-3">
                      <span
                        className={clsx(
                          "mt-1.5 h-2 w-2 rounded-full",
                          event.tone === "success"
                            ? "bg-emerald-500"
                            : event.tone === "warning"
                              ? "bg-amber-500"
                              : event.tone === "danger"
                                ? "bg-rose-500"
                                : "bg-muted-foreground",
                        )}
                      />
                      <div className="flex flex-1 items-center justify-between gap-3">
                        <span className="font-semibold text-foreground">{event.label}</span>
                        <span>{formatTime(event.at)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p>No recent activity yet.</p>
                )}
                {runLoading ? <p className="text-[11px] text-muted-foreground">Refreshing run status…</p> : null}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card px-8 py-12 text-center">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="text-sm text-muted-foreground">{description}</p>
      {action ? (
        <Button type="button" onClick={action.onClick} size="sm" className="text-xs">
          {action.label}
        </Button>
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: DocumentStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={clsx("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold", style.pill)}>
      <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}

function MappingBadge({ mapping }: { mapping: MappingHealth }) {
  if (mapping.pending && mapping.attention === 0 && mapping.unmapped === 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
        <AlertIcon className="h-3 w-3" />
        Mapping pending
      </span>
    );
  }
  if (mapping.attention === 0 && mapping.unmapped === 0) {
    return null;
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
      <AlertIcon className="h-3 w-3" />
      {mapping.attention > 0 ? `${mapping.attention} columns need attention` : `${mapping.unmapped} unmapped columns`}
    </span>
  );
}

function PreviewTable({ sheet }: { sheet: WorkbookSheet }) {
  return (
    <table className="min-w-full text-left text-xs">
      <thead className="sticky top-0 bg-muted text-muted-foreground">
        <tr>
          {sheet.headers.map((column, index) => (
            <th key={`${column}-${index}`} className="px-3 py-2 font-semibold uppercase tracking-wide">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sheet.rows.map((row, rowIndex) => (
          <tr key={`${sheet.name}-${rowIndex}`} className="border-t border-border">
            {row.map((cell, cellIndex) => (
              <td key={`${sheet.name}-${rowIndex}-${cellIndex}`} className="px-3 py-2 text-foreground">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: { sort: string | null; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<DocumentPage> {
  const query: ListDocumentsQuery = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : DOCUMENTS_PAGE_SIZE,
    include_total: false,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document page payload.");
  }

  return data;
}

async function fetchWorkbookPreview(url: string, signal?: AbortSignal): Promise<WorkbookPreview> {
  const response = await fetch(url, { credentials: "include", signal });
  if (!response.ok) {
    throw new Error("Unable to fetch processed workbook.");
  }
  const buffer = await response.arrayBuffer();
  const XLSX = await import("xlsx");
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheets = workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name];
    const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false, blankrows: false }) as unknown[][];
    const totalRows = rows.length;
    const totalColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
    const truncatedRows = totalRows > MAX_PREVIEW_ROWS;
    const truncatedColumns = totalColumns > MAX_PREVIEW_COLUMNS;
    const visibleRows = rows.slice(0, MAX_PREVIEW_ROWS).map((row) =>
      row.slice(0, MAX_PREVIEW_COLUMNS).map((cell) => normalizeCell(cell)),
    );
    const columnCount = Math.max(visibleRows[0]?.length ?? 0, totalColumns, 1);
    const headers = buildHeaders(visibleRows[0] ?? [], columnCount);
    const bodyRows = visibleRows.slice(1).map((row) => normalizeRow(row, headers.length));
    return {
      name,
      headers,
      rows: bodyRows,
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns,
    } satisfies WorkbookSheet;
  });

  return { sheets };
}

function buildDocumentEntry(
  document: DocumentRecord,
  options: { upload?: UploadQueueItem<DocumentUploadResponse> } = {},
): DocumentEntry {
  const status = mapApiStatus(document.status);
  const owner = deriveOwnerLabel(document);
  const createdAt = parseTimestamp(document.created_at);
  const updatedAt = parseTimestamp(document.updated_at);
  const stage = buildStageLabel(status, document.last_run);
  const mapping = deriveMappingHealth(document);

  return {
    id: document.id,
    name: document.name,
    status,
    owner,
    tags: document.tags ?? [],
    createdAt,
    updatedAt,
    size: formatBytes(document.byte_size),
    stage,
    error: status === "failed" ? buildDocumentError(document) : undefined,
    mapping,
    history: buildDocumentHistory(document, owner),
    record: document,
    upload: options.upload,
  };
}

function buildUploadEntry(
  item: UploadQueueItem<DocumentUploadResponse>,
  ownerLabel: string,
  createdAt: number,
): DocumentEntry {
  const isFailed = item.status === "failed";
  const isUploading = item.status === "uploading";
  const status: DocumentStatus = isFailed ? "failed" : isUploading ? "processing" : "queued";
  const progress = isUploading ? item.progress.percent : undefined;
  const stage = isFailed ? "Upload failed" : isUploading ? "Uploading" : "Queued for upload";
  const error = isFailed
    ? {
        summary: item.error ?? "Upload failed",
        detail: "We could not upload this file. Check the connection and retry.",
        nextStep: "Retry now or remove the upload.",
      }
    : undefined;
  const historyLabel = isFailed ? "Upload failed" : isUploading ? "Uploading" : "Queued for upload";

  return {
    id: item.id,
    name: item.file.name,
    status,
    owner: ownerLabel,
    tags: [],
    createdAt,
    updatedAt: createdAt,
    size: formatBytes(item.file.size),
    progress,
    stage,
    error,
    mapping: { attention: 0, unmapped: 0, pending: true },
    history: [
      {
        id: `${item.id}-upload`,
        label: historyLabel,
        at: createdAt,
        tone: isFailed ? "danger" : "info",
      },
    ],
    upload: item,
  };
}

function mapApiStatus(status: ApiDocumentStatus): DocumentStatus {
  switch (status) {
    case "processed":
      return "ready";
    case "processing":
      return "processing";
    case "failed":
      return "failed";
    case "archived":
      return "archived";
    case "uploaded":
      return "queued";
    default:
      return "queued";
  }
}

function deriveOwnerLabel(document: DocumentRecord): string | null {
  const metadata = document.metadata ?? {};
  const ownerFromMetadata = readOwnerFromMetadata(metadata);
  if (ownerFromMetadata) {
    return ownerFromMetadata;
  }
  const uploader = document.uploader;
  if (uploader?.name || uploader?.email) {
    return uploader.name ?? uploader.email ?? "Unassigned";
  }
  return null;
}

function readOwnerFromMetadata(metadata: Record<string, unknown>): string | null {
  const ownerName = typeof metadata.owner === "string" ? metadata.owner : undefined;
  const ownerEmail = typeof metadata.owner_email === "string" ? metadata.owner_email : undefined;
  if (ownerName || ownerEmail) {
    return ownerName ?? ownerEmail ?? null;
  }
  return null;
}

function deriveMappingHealth(document: DocumentRecord): MappingHealth {
  const metadata = document.metadata ?? {};
  const fromMetadata = readMappingFromMetadata(metadata);
  if (fromMetadata) {
    return fromMetadata;
  }
  if (document.status === "uploaded" || document.status === "processing") {
    return { attention: 0, unmapped: 0, pending: true };
  }
  return { attention: 0, unmapped: 0 };
}

function readMappingFromMetadata(metadata: Record<string, unknown>): MappingHealth | null {
  const candidate = metadata.mapping ?? metadata.mapping_health ?? metadata.mapping_quality;
  if (candidate && typeof candidate === "object") {
    const record = candidate as Record<string, unknown>;
    const attention =
      typeof record.issues === "number"
        ? record.issues
        : typeof record.attention === "number"
          ? record.attention
          : 0;
    const unmapped = typeof record.unmapped === "number" ? record.unmapped : 0;
    const pending = typeof record.status === "string" && record.status === "pending";
    return { attention, unmapped, pending: pending || undefined };
  }

  const attention = typeof metadata.mapping_issues === "number" ? metadata.mapping_issues : null;
  const unmapped = typeof metadata.unmapped_columns === "number" ? metadata.unmapped_columns : null;
  if (attention !== null || unmapped !== null) {
    return { attention: attention ?? 0, unmapped: unmapped ?? 0 };
  }

  return null;
}

function buildDocumentHistory(document: DocumentRecord, ownerLabel: string | null): DocumentHistoryItem[] {
  const createdAt = parseTimestamp(document.created_at);
  const history: DocumentHistoryItem[] = [
    {
      id: `${document.id}-uploaded`,
      label: ownerLabel ? `Uploaded by ${ownerLabel}` : "Uploaded",
      at: createdAt,
      tone: "info",
    },
  ];

  if (document.last_run) {
    const runAt = parseTimestamp(document.last_run.run_at ?? document.last_run_at ?? document.updated_at);
    const runEntry = buildRunHistoryEntry(document.id, document.last_run, runAt);
    if (runEntry) {
      history.push(runEntry);
    }
  } else if (document.last_run_at) {
    history.push({
      id: `${document.id}-run`,
      label: "Run updated",
      at: parseTimestamp(document.last_run_at),
      tone: "info",
    });
  }

  if (document.status === "archived") {
    history.push({
      id: `${document.id}-archived`,
      label: "Archived",
      at: parseTimestamp(document.updated_at),
      tone: "warning",
    });
  }

  return history.length > 6 ? history.slice(history.length - 6) : history;
}

function buildRunHistoryEntry(docId: string, lastRun: DocumentLastRun, runAt: number): DocumentHistoryItem | null {
  const meta = describeRunStatus(lastRun.status);
  if (!meta) {
    return null;
  }
  const message = lastRun.message?.trim();
  const label = message ? `${meta.label}: ${message}` : meta.label;
  return { id: `${docId}-${lastRun.status}-${runAt}`, label, at: runAt, tone: meta.tone };
}

function describeRunStatus(status: RunStatus | null | undefined) {
  if (!status) {
    return null;
  }
  switch (status) {
    case "queued":
      return { label: "Queued for processing", tone: "info" as const };
    case "running":
      return { label: "Processing started", tone: "info" as const };
    case "succeeded":
      return { label: "Output ready", tone: "success" as const };
    case "failed":
      return { label: "Processing failed", tone: "danger" as const };
    case "cancelled":
      return { label: "Run cancelled", tone: "warning" as const };
    default:
      return { label: "Run updated", tone: "info" as const };
  }
}

function buildStageLabel(status: DocumentStatus, lastRun: DocumentLastRun | null | undefined) {
  if (status === "queued") {
    return "Queued for processing";
  }
  if (status === "processing") {
    if (lastRun?.status === "queued") {
      return "Queued for processing";
    }
    return "Processing output";
  }
  return undefined;
}

function buildDocumentError(document: DocumentRecord): DocumentError {
  const message = document.last_run?.message?.trim();
  return {
    summary: message ?? "Processing failed",
    detail: message ?? "We could not complete normalization for this file.",
    nextStep: "Retry now or fix mapping later.",
  };
}

async function downloadProcessedOutput(runId: string, fallbackName: string): Promise<string> {
  const run = await fetchRun(runId);
  const outputUrl = runOutputUrl(run);
  if (!outputUrl) {
    throw new Error("Processed output is not ready yet.");
  }
  const response = await fetch(outputUrl, { credentials: "include" });
  if (!response.ok) {
    throw new Error("Unable to download processed output.");
  }
  const blob = await response.blob();
  const filename =
    extractFilename(response.headers.get("content-disposition")) ??
    run.output?.filename ??
    buildNormalizedFilename(fallbackName);
  triggerDownload(blob, filename);
  return filename;
}

function extractFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) {
    return null;
  }
  const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) {
    return decodeURIComponent(utfMatch[1]);
  }
  const match = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
  return match?.[1] ?? null;
}

function buildNormalizedFilename(name: string) {
  const base = name.replace(/\.[^.]+$/, "");
  return `${base}_normalized.xlsx`;
}

function triggerDownload(blob: Blob, fileName: string) {
  if (typeof window === "undefined") {
    return;
  }
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
}

function normalizeCell(value: unknown) {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value instanceof Date) {
    return value.toLocaleDateString();
  }
  return String(value);
}

function normalizeRow(row: string[], length: number) {
  if (row.length >= length) {
    return row;
  }
  return row.concat(Array.from({ length: length - row.length }, () => ""));
}

function buildHeaders(raw: string[], totalColumns: number) {
  const trimmed = raw.map((cell) => cell.trim());
  const hasNamed = trimmed.some(Boolean);
  const headerCount = Math.max(trimmed.length, totalColumns);
  const headers = hasNamed ? trimmed : Array.from({ length: headerCount }, (_, index) => columnLabel(index));
  return normalizeRow(headers, headerCount);
}

function columnLabel(index: number) {
  let label = "";
  let n = index + 1;
  while (n > 0) {
    const remainder = (n - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    n = Math.floor((n - 1) / 26);
  }
  return `Column ${label}`;
}

function isAttention(doc: DocumentEntry) {
  return doc.status === "failed" || doc.mapping.attention > 0 || doc.mapping.unmapped > 0;
}

function getStatusDescription(doc: DocumentEntry, run?: RunResource | null) {
  switch (doc.status) {
    case "ready":
      return "Processed XLSX ready to download.";
    case "processing":
      if (run?.status === "queued") {
        return "Queued for processing.";
      }
      if (run?.status === "running") {
        return "Processing in progress.";
      }
      return doc.stage ? `${doc.stage}.` : "Processing in progress.";
    case "failed":
      return doc.error?.summary ?? doc.record?.last_run?.message ?? "Needs attention.";
    case "queued":
      return "Queued and waiting to start.";
    case "archived":
      return "Archived output (read-only).";
    default:
      return "";
  }
}

function getMappingHealthLabel(mapping: MappingHealth) {
  if (mapping.pending && mapping.attention === 0 && mapping.unmapped === 0) {
    return "Mapping pending";
  }
  if (mapping.attention > 0) {
    return `${mapping.attention} columns need attention`;
  }
  if (mapping.unmapped > 0) {
    return `${mapping.unmapped} unmapped columns`;
  }
  return "Mapping healthy";
}

function formatRelativeTime(nowTimestamp: number, timestamp: number) {
  const diff = Math.max(0, nowTimestamp - timestamp);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function parseTimestamp(value: string | null | undefined) {
  const parsed = value ? Date.parse(value) : NaN;
  return Number.isNaN(parsed) ? Date.now() : parsed;
}

function formatTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function formatBytes(bytes: number) {
  if (bytes === 0) {
    return "0 B";
  }
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  const value = bytes / Math.pow(k, i);
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${sizes[i]}`;
}

function getInitials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function readSavedViews(): SavedView[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
  } catch {
    return [];
  }
}

function writeSavedViews(views: SavedView[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v5a1 1 0 0 0 1 1h5" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M11 4a7 7 0 1 1 0 14a7 7 0 0 1 0-14Z" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 16V4" />
      <path d="m6 10 6-6 6 6" />
      <path d="M4 20h16" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 4v12" />
      <path d="m6 10 6 6 6-6" />
      <path d="M4 20h16" />
    </svg>
  );
}

function RetryIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M20 12a8 8 0 1 1-2.34-5.66" />
      <path d="M20 4v6h-6" />
    </svg>
  );
}

function GridIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function BoardIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <rect x="4" y="4" width="7" height="16" rx="1.5" />
      <rect x="13" y="4" width="7" height="9" rx="1.5" />
      <rect x="13" y="15" width="7" height="5" rx="1.5" />
    </svg>
  );
}

function TagIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M3 11V4a1 1 0 0 1 1-1h7l9 9-7 7-9-9Z" />
      <path d="M7.5 7.5h.01" />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.6 2.5 18a1 1 0 0 0 .9 1.5h17.2a1 1 0 0 0 .9-1.5l-7.8-14.4a1 1 0 0 0-1.4 0Z" />
    </svg>
  );
}
