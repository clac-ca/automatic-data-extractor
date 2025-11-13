// route.tsx — Workspace Documents (polished, compact UI)

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useId,
  type ChangeEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";

import { useSearchParams } from "@app/nav/urlState";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useConfigsQuery } from "@shared/configs";
import { client } from "@shared/api/client";
import { useFlattenedPages } from "@shared/api/pagination";
import { createScopedStorage } from "@shared/storage";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import type { components, paths } from "@schema";

import { Alert } from "@ui/Alert";
import { Input } from "@ui/Input";
import { Select } from "@ui/Select";
import { Button } from "@ui/Button";

/* -------------------------------- Types & constants ------------------------------- */

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type JobRecord = components["schemas"]["JobRecord"];
type JobSubmissionPayload = components["schemas"]["JobSubmissionRequest"];
type DocumentListPage = components["schemas"]["DocumentPage"];

type ListDocumentsParameters = paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"];
type ListDocumentsQuery = ListDocumentsParameters extends { query?: infer Q }
  ? (Q extends undefined ? Record<string, never> : Q)
  : Record<string, never>;

type ListJobsParameters = paths["/api/v1/workspaces/{workspace_id}/jobs"]["get"]["parameters"];
type ListJobsQuery = ListJobsParameters extends { query?: infer Q }
  ? (Q extends undefined ? Record<string, never> : Q)
  : Record<string, never>;

type JobStatus = JobRecord["status"];
type StatusFilterInput = DocumentStatus | DocumentStatus[] | null | undefined;

type StatusOptionValue = "all" | DocumentStatus;

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

const SORT_OPTIONS = ["-created_at", "created_at", "name", "-name", "status"] as const;
type SortOption = (typeof SORT_OPTIONS)[number];

function parseStatus(value: string | null): StatusOptionValue {
  const allowed = new Set<StatusOptionValue>([
    "all",
    "uploaded",
    "processing",
    "processed",
    "failed",
    "archived",
  ]);
  return allowed.has((value as StatusOptionValue) ?? "all")
    ? ((value as StatusOptionValue) ?? "all")
    : "all";
}

function parseSort(value: string | null): SortOption {
  const allowed = new Set<string>(SORT_OPTIONS);
  return (allowed.has(value ?? "") ? (value as SortOption) : "-created_at") as SortOption;
}

const uploadedFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const documentsKeys = {
  all: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.all(), workspaceId] as const,
  list: (workspaceId: string, status: DocumentStatus[] | null, search: string | null, sort: string | null) =>
    [...documentsKeys.workspace(workspaceId), "list", { status, search, sort }] as const,
};

const DOCUMENTS_PAGE_SIZE = 50;

const jobsKeys = {
  root: (workspaceId: string) => ["jobs", workspaceId] as const,
  document: (workspaceId: string, documentId: string, limit: number) =>
    [...jobsKeys.root(workspaceId), "document", documentId, limit] as const,
};
/* -------------------------------- Route component -------------------------------- */

export default function WorkspaceDocumentsRoute() {
  const { workspace } = useWorkspaceContext();

  // URL-synced state
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState<StatusOptionValue>(parseStatus(searchParams.get("status")));
  const [sortOrder, setSortOrder] = useState<SortOption>(parseSort(searchParams.get("sort")));
  const [searchTerm, setSearchTerm] = useState(searchParams.get("q") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(searchTerm.trim());

  // File input + selection
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const selectedIdsSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedIdsArray = useMemo(() => Array.from(selectedIdsSet), [selectedIdsSet]);
  const selectedCount = selectedIdsSet.size;

  // Operations
  const uploadDocuments = useUploadWorkspaceDocuments(workspace.id);
  const deleteDocuments = useDeleteWorkspaceDocuments(workspace.id);
  const safeModeStatus = useSafeModeStatus();
  const safeModeEnabled = safeModeStatus.data?.enabled ?? false;
  const safeModeDetail = safeModeStatus.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const safeModeLoading = safeModeStatus.isPending;

  const [banner, setBanner] = useState<{ tone: "error"; message: string } | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [runDrawerDocument, setRunDrawerDocument] = useState<DocumentRecord | null>(null);

  const isUploading = uploadDocuments.isPending;
  const isDeleting = deleteDocuments.isPending;

  // Query
  const documentsQuery = useWorkspaceDocuments(workspace.id, {
    status: statusFilter,
    search: debouncedSearch,
    sort: sortOrder,
  });
  const { refetch: refetchDocuments } = documentsQuery;
  const getDocumentKey = useCallback((document: DocumentRecord) => document.id, []);
  const documents = useFlattenedPages(documentsQuery.data?.pages, getDocumentKey);
  const fetchingNextPage = documentsQuery.isFetchingNextPage;
  const backgroundFetch = documentsQuery.isFetching && !fetchingNextPage;

  /* ----------------------------- URL sync ----------------------------- */
  useEffect(() => {
    const s = new URLSearchParams();
    if (statusFilter !== "all") s.set("status", statusFilter);
    if (sortOrder !== "-created_at") s.set("sort", sortOrder);
    if (debouncedSearch) s.set("q", debouncedSearch);
    setSearchParams(s, { replace: true });
  }, [statusFilter, sortOrder, debouncedSearch, setSearchParams]);

  /* --------------------------- Search debounce --------------------------- */
  useEffect(() => {
    const h = window.setTimeout(() => setDebouncedSearch(searchTerm.trim()), 250);
    return () => window.clearTimeout(h);
  }, [searchTerm]);

  /* ------------------------- Selection integrity ------------------------- */
  useEffect(() => {
    setSelectedIds((current) => {
      if (current.size === 0) return current;
      const next = new Set<string>();
      const valid = new Set(documents.map((d) => d.id));
      let changed = false;
      for (const id of current) {
        if (valid.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [documents]);

  const firstSelectedDocument = useMemo(() => {
    for (const d of documents) if (selectedIdsSet.has(d.id)) return d;
    return null;
  }, [documents, selectedIdsSet]);

  /* --------------------------- Keyboard shortcuts --------------------------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Upload
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "u") {
        e.preventDefault();
        fileInputRef.current?.click();
        return;
      }
      // Delete selection
      if ((e.key === "Delete" || e.key === "Backspace") && selectedCount > 0) {
        e.preventDefault();
        void handleDeleteSelected();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCount]);

  /* ------------------------------- Helpers ------------------------------- */

  const statusFormatter = useCallback(
    (status: DocumentStatus) => DOCUMENT_STATUS_LABELS[status] ?? status,
    [],
  );

  const renderJobStatus = useCallback(
    (documentItem: DocumentRecord) => (
      <DocumentJobStatus workspaceId={workspace.id} documentId={documentItem.id} />
    ),
    [workspace.id],
  );

  const handleOpenFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUploadFiles = useCallback(
    async (files: readonly File[]) => {
      if (!files.length) return;
      setBanner(null);
      try {
        await uploadDocuments.mutateAsync({ files });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to upload documents.";
        setBanner({ tone: "error", message });
      }
    },
    [uploadDocuments],
  );

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    await handleUploadFiles(files);
    event.target.value = "";
  };

  const handleToggleDocument = (documentId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(documentId)) next.delete(documentId);
      else next.add(documentId);
      return next;
    });
  };

  const handleToggleAll = () => {
    setSelectedIds((current) => {
      if (documents.length === 0) return new Set();
      const allIds = documents.map((doc) => doc.id);
      if (current.size === documents.length && allIds.every((id) => current.has(id))) return new Set();
      return new Set(allIds);
    });
  };

  const handleDeleteSelected = useCallback(async () => {
    const ids = selectedIdsArray;
    if (!ids.length) return;
    setBanner(null);
    try {
      await deleteDocuments.mutateAsync({ documentIds: ids });
      setSelectedIds(new Set());
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to delete documents.";
      setBanner({ tone: "error", message });
    }
  }, [deleteDocuments, selectedIdsArray]);

  const handleDeleteSingle = useCallback(
    async (document: DocumentRecord) => {
      setBanner(null);
      try {
        await deleteDocuments.mutateAsync({ documentIds: [document.id] });
        setSelectedIds((current) => {
          const next = new Set(current);
          next.delete(document.id);
          return next;
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to delete document.";
        setBanner({ tone: "error", message });
      }
    },
    [deleteDocuments],
  );

  const handleDownloadDocument = useCallback(
    async (document: DocumentRecord) => {
      try {
        setDownloadingId(document.id);
        const { blob, filename } = await downloadDocument(workspace.id, document.id);
        triggerBrowserDownload(blob, filename ?? document.name);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to download document.";
        setBanner({ tone: "error", message });
      } finally {
        setDownloadingId(null);
      }
    },
    [workspace.id],
  );

  const handleOpenRunDrawer = useCallback((document: DocumentRecord) => {
    setRunDrawerDocument(document);
  }, []);

  const handleRunSuccess = useCallback(() => {
    void refetchDocuments();
  }, [refetchDocuments]);

  const handleRunError = useCallback((message: string) => {
    setBanner({ tone: "error", message });
  }, []);

  const onResetFilters = () => {
    setSearchTerm("");
    setStatusFilter("all");
    setSortOrder("-created_at");
  };

  const isDefaultFilters = statusFilter === "all" && sortOrder === "-created_at" && !debouncedSearch;

  /* -------------------------------- Render -------------------------------- */

  return (
    <>
      {/* Global drop-anywhere overlay */}
      <DropAnywhereOverlay
        workspaceName={workspace.name ?? undefined}
        disabled={isUploading}
        onFiles={async (files) => {
          await handleUploadFiles(files);
        }}
      />

      <div className="space-y-4">
        {/* Hidden file input (paired with Upload) */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Compact Page Bar (title + filters + Upload) */}
        <DocumentsToolbar
          title="Documents"
          subtitle={`Manage uploads and runs across ${workspace.name ?? "this workspace"}.`}
          search={searchTerm}
          onSearch={setSearchTerm}
          status={statusFilter}
          onStatus={setStatusFilter}
          sort={sortOrder}
          onSort={setSortOrder}
          onReset={onResetFilters}
          isFetching={documentsQuery.isFetching}
          isDefault={isDefaultFilters}
          onUploadClick={handleOpenFilePicker}
          uploadDisabled={isUploading}
        />

        {/* Inline error banner */}
        {banner ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
            {banner.message}
          </div>
        ) : null}

        {/* Content panel */}
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 sm:p-4">
          {documentsQuery.isLoading ? (
            <SkeletonList />
          ) : documentsQuery.isError ? (
            <p className="text-rose-600">Failed to load documents.</p>
          ) : documents.length === 0 ? (
            <EmptyState onUploadClick={handleOpenFilePicker} />
          ) : (
            <>
              <DocumentsTable
                documents={documents}
                selectedIds={selectedIdsSet}
                onToggleDocument={handleToggleDocument}
                onToggleAll={handleToggleAll}
                disableSelection={backgroundFetch || isDeleting || uploadDocuments.isPending}
                disableRowActions={deleteDocuments.isPending}
                formatStatusLabel={statusFormatter}
                onDeleteDocument={handleDeleteSingle}
                onDownloadDocument={handleDownloadDocument}
                onRunDocument={handleOpenRunDrawer}
                downloadingId={downloadingId}
                renderJobStatus={renderJobStatus}
                safeModeEnabled={safeModeEnabled}
                safeModeMessage={safeModeDetail}
                safeModeLoading={safeModeLoading}
              />
              {documentsQuery.hasNextPage ? (
                <div className="flex justify-center border-t border-slate-200 pt-3">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => documentsQuery.fetchNextPage()}
                    disabled={fetchingNextPage}
                  >
                    {fetchingNextPage ? "Loading more documents…" : "Load more documents"}
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      {/* Bottom bulk action bar */}
      <BulkBar
        count={selectedCount}
        onClear={() => setSelectedIds(new Set())}
        onRun={() => {
          if (firstSelectedDocument && !safeModeEnabled && !safeModeLoading) {
            handleOpenRunDrawer(firstSelectedDocument);
          }
        }}
        onDelete={handleDeleteSelected}
        busy={isDeleting}
        safeModeEnabled={safeModeEnabled}
        safeModeMessage={safeModeDetail}
        safeModeLoading={safeModeLoading}
      />

      {/* Run drawer */}
      <RunExtractionDrawer
        open={Boolean(runDrawerDocument)}
        workspaceId={workspace.id}
        documentRecord={runDrawerDocument}
        onClose={() => setRunDrawerDocument(null)}
        onRunSuccess={handleRunSuccess}
        onRunError={handleRunError}
        safeModeEnabled={safeModeEnabled}
        safeModeMessage={safeModeDetail}
        safeModeLoading={safeModeLoading}
      />
    </>
  );
}
/* ------------------------------- Data hooks ------------------------------- */

interface WorkspaceDocumentsOptions {
  readonly status: StatusOptionValue;
  readonly search: string;
  readonly sort: SortOption;
}

function useWorkspaceDocuments(workspaceId: string, options: WorkspaceDocumentsOptions) {
  const statusFilter = options.status === "all" ? undefined : options.status;
  const normalizedStatus = normaliseStatusFilter(statusFilter) ?? null;
  const search = options.search.trim() || null;
  const sort = options.sort.trim() || null;

  return useInfiniteQuery<DocumentListPage>({
    queryKey: documentsKeys.list(workspaceId, normalizedStatus, search, sort),
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          status: normalizedStatus,
          search,
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
  });
}

function useUploadWorkspaceDocuments(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { files: readonly File[] }>({
    mutationFn: async ({ files }) => {
      const uploads = Array.from(files);
      for (const file of uploads) {
        await client.POST("/api/v1/workspaces/{workspace_id}/documents", {
          params: { path: { workspace_id: workspaceId } },
          body: { file: "" },
          bodySerializer: () => {
            const formData = new FormData();
            formData.append("file", file);
            return formData;
          },
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useDeleteWorkspaceDocuments(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { documentIds: readonly string[] }>({
    mutationFn: async ({ documentIds }) => {
      await Promise.all(
        documentIds.map((documentId) =>
          client.DELETE("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
            params: { path: { workspace_id: workspaceId, document_id: documentId } },
          })
        )
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useSubmitJob(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<JobRecord, Error, JobSubmissionPayload>({
    mutationFn: async (payload) => {
      const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/jobs", {
        params: { path: { workspace_id: workspaceId } },
        body: payload,
      });
      if (!data) throw new Error("Expected job payload.");
      return data as JobRecord;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: jobsKeys.root(workspaceId) });
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useDocumentJobs(workspaceId: string, documentId: string, options?: { limit?: number; enabled?: boolean }) {
  const { limit = 3, enabled = true } = options ?? {};

  return useQuery<JobRecord[]>({
    queryKey: jobsKeys.document(workspaceId, documentId, limit),
    queryFn: ({ signal }) => listWorkspaceJobs(workspaceId, { inputDocumentId: documentId, limit }, signal),
    enabled: enabled && workspaceId.length > 0 && documentId.length > 0,
    staleTime: 10_000,
    placeholderData: (previous) => previous ?? [],
  });
}

function useDocumentRunPreferences(workspaceId: string, documentId: string) {
  const storage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspaceId}.document_runs`),
    [workspaceId],
  );

  const [preferences, setPreferencesState] = useState<DocumentRunPreferences>(() =>
    readRunPreferences(storage, documentId),
  );

  useEffect(() => {
    setPreferencesState(readRunPreferences(storage, documentId));
  }, [storage, documentId]);

  const setPreferences = useCallback(
    (next: DocumentRunPreferences) => {
      setPreferencesState(next);
      const all = storage.get<Record<string, DocumentRunPreferences>>() ?? {};
      storage.set({
        ...all,
        [documentId]: {
          configId: next.configId,
          configVersionId: next.configVersionId,
        },
      });
    },
    [storage, documentId],
  );

  return { preferences, setPreferences } as const;
}

type DocumentRunPreferences = {
  readonly configId: string | null;
  readonly configVersionId: string | null;
};
/* ------------------------ API helpers & small utilities ------------------------ */

async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: {
    status: DocumentStatus[] | null;
    search: string | null;
    sort: string | null;
    page: number;
    pageSize: number;
  },
  signal?: AbortSignal,
): Promise<DocumentListPage> {
  const query: ListDocumentsQuery = {};
  if (options.status && options.status.length > 0) query.status = Array.from(options.status);
  if (options.search) query.q = options.search;
  if (options.sort) query.sort = options.sort;
  if (options.page && options.page > 0) {
    query.page = options.page;
  }
  if (options.pageSize && options.pageSize > 0) {
    query.page_size = options.pageSize;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document page payload.");
  }

  return data;
}

async function listWorkspaceJobs(
  workspaceId: string,
  options: { status?: JobStatus | "all" | null; inputDocumentId?: string | null; limit?: number | null; offset?: number | null },
  signal?: AbortSignal,
): Promise<JobRecord[]> {
  const query: ListJobsQuery = {};
  if (options.status && options.status !== "all") query.status = options.status;
  if (options.inputDocumentId) query.input_document_id = options.inputDocumentId;
  if (typeof options.limit === "number") query.limit = options.limit;
  if (typeof options.offset === "number") query.offset = options.offset;

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/jobs", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  return (data ?? []) as JobRecord[];
}

async function downloadDocument(workspaceId: string, documentId: string) {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download",
    {
      params: { path: { workspace_id: workspaceId, document_id: documentId } },
      parseAs: "blob",
    },
  );
  if (!data) throw new Error("Expected document download payload.");
  const filename = extractFilename(response.headers.get("content-disposition")) ?? `document-${documentId}`;
  return { blob: data, filename };
}

function extractFilename(header: string | null) {
  if (!header) return null;
  const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }
  const filenameMatch = header.match(/filename="?([^";]+)"?/i);
  return filenameMatch?.[1] ?? null;
}

function normaliseStatusFilter(status: StatusFilterInput) {
  if (status == null) return undefined;
  if (Array.isArray(status)) {
    const filtered = status.filter((value): value is DocumentStatus => Boolean(value));
    return filtered.length > 0 ? filtered : undefined;
  }
  return [status];
}

function readRunPreferences(
  storage: ReturnType<typeof createScopedStorage>,
  documentId: string,
): DocumentRunPreferences {
  const all = storage.get<Record<string, DocumentRunPreferences>>();
  if (all && typeof all === "object" && documentId in all) {
    const entry = all[documentId];
    if (entry && typeof entry === "object") {
      return {
        configId: entry.configId ?? null,
        configVersionId: entry.configVersionId ?? null,
      };
    }
  }
  return { configId: null, configVersionId: null };
}
/* ------------------------- Compact Page Bar / Toolbar ------------------------- */

function DocumentsToolbar({
  title,
  subtitle,
  search,
  onSearch,
  status,
  onStatus,
  sort,
  onSort,
  onReset,
  isFetching,
  isDefault,
  onUploadClick,
  uploadDisabled,
}: {
  title?: string;
  subtitle?: string;
  search: string;
  onSearch: (v: string) => void;
  status: StatusOptionValue;
  onStatus: (v: StatusOptionValue) => void;
  sort: SortOption;
  onSort: (v: SortOption) => void;
  onReset: () => void;
  isFetching?: boolean;
  isDefault: boolean;
  onUploadClick: () => void;
  uploadDisabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const searchId = useId();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if ((key === "/" || ((e.metaKey || e.ctrlKey) && key === "k")) && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (key === "escape" && document.activeElement === inputRef.current && search) onSearch("");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [search, onSearch]);

  return (
    <section
      className="rounded-xl border border-slate-200 bg-white/95 p-3 sm:p-4"
      role="region"
      aria-label="Documents header and filters"
    >
      {/* Top row: title on the left, Upload on the right */}
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-slate-900 sm:text-xl">
            {title ?? "Documents"}
          </h1>
          {subtitle ? (
            <p className="mt-0.5 hidden truncate text-xs text-slate-600 sm:block">{subtitle}</p>
          ) : null}
        </div>
        <Button
          className="shrink-0"
          onClick={onUploadClick}
          disabled={uploadDisabled}
          isLoading={uploadDisabled}
          aria-label="Upload documents"
        >
          Upload
        </Button>
      </div>

      {/* Filters row */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr,auto,auto,auto] sm:items-center sm:gap-3">
        <div className="relative">
          <Input
            id={searchId}
            ref={inputRef}
            type="search"
            placeholder="Search (⌘K or /)"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full"
            aria-label="Search documents"
          />
          {search ? (
            <button
              type="button"
              onClick={() => onSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1 text-xs text-slate-500 hover:text-slate-800"
              title="Clear (Esc)"
              aria-label="Clear search"
            >
              ×
            </button>
          ) : null}
        </div>

        <Select
          value={status}
          onChange={(e) => onStatus(e.target.value as StatusOptionValue)}
          className="w-full sm:w-[170px]"
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="processing">{DOCUMENT_STATUS_LABELS.processing}</option>
          <option value="failed">{DOCUMENT_STATUS_LABELS.failed}</option>
          <option value="uploaded">{DOCUMENT_STATUS_LABELS.uploaded}</option>
          <option value="processed">{DOCUMENT_STATUS_LABELS.processed}</option>
          <option value="archived">{DOCUMENT_STATUS_LABELS.archived}</option>
        </Select>

        <Select
          value={sort}
          onChange={(e) => onSort(e.target.value as SortOption)}
          className="w-full sm:w-[170px]"
          aria-label="Sort documents"
        >
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="name">Name A–Z</option>
          <option value="-name">Name Z–A</option>
          <option value="status">Status</option>
        </Select>

        <div className="flex items-center gap-3 sm:justify-end">
          <button
            type="button"
            onClick={onReset}
            disabled={isDefault}
            className={clsx(
              "rounded text-sm",
              isDefault
                ? "cursor-default text-slate-300"
                : "text-slate-600 underline underline-offset-4 hover:text-slate-900"
            )}
            title="Reset filters"
          >
            Reset
          </button>
          <span
            className={clsx(
              "inline-flex items-center justify-end gap-1 text-xs text-slate-500",
              isFetching ? "opacity-100" : "opacity-0"
            )}
            role="status"
            aria-live="polite"
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
            Updating…
          </span>
        </div>
      </div>
    </section>
  );
}
/* ----------------------------- Documents table ----------------------------- */

interface DocumentsTableProps {
  readonly documents: readonly DocumentRecord[];
  readonly selectedIds: ReadonlySet<string>;
  readonly onToggleDocument: (documentId: string) => void;
  readonly onToggleAll: () => void;
  readonly disableSelection?: boolean;
  readonly disableRowActions?: boolean;
  readonly formatStatusLabel?: (status: DocumentRecord["status"]) => string;
  readonly onDeleteDocument?: (document: DocumentRecord) => void;
  readonly onDownloadDocument?: (document: DocumentRecord) => void;
  readonly onRunDocument?: (document: DocumentRecord) => void;
  readonly downloadingId?: string | null;
  readonly renderJobStatus?: (document: DocumentRecord) => ReactNode;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function DocumentsTable({
  documents,
  selectedIds,
  onToggleDocument,
  onToggleAll,
  disableSelection = false,
  disableRowActions = false,
  formatStatusLabel,
  onDeleteDocument,
  onDownloadDocument,
  onRunDocument,
  downloadingId = null,
  renderJobStatus,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DocumentsTableProps) {
  const headerCheckboxRef = useRef<HTMLInputElement | null>(null);

  const { allSelected, someSelected } = useMemo(() => {
    if (documents.length === 0) return { allSelected: false, someSelected: false };
    const selectedCount = documents.reduce(
      (count, d) => (selectedIds.has(d.id) ? count + 1 : count),
      0,
    );
    return { allSelected: selectedCount === documents.length, someSelected: selectedCount > 0 && selectedCount < documents.length };
  }, [documents, selectedIds]);

  useEffect(() => {
    if (headerCheckboxRef.current) headerCheckboxRef.current.indeterminate = someSelected;
  }, [someSelected]);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full table-fixed border-separate border-spacing-0 text-sm text-slate-700">
        <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-[11px] font-medium text-slate-500">
          <tr className="border-b border-slate-200">
            <th scope="col" className="w-10 px-2.5 py-2">
              <input
                ref={headerCheckboxRef}
                type="checkbox"
                className="h-4 w-4 rounded border border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                checked={allSelected}
                onChange={onToggleAll}
                disabled={disableSelection || documents.length === 0}
              />
            </th>
            <th scope="col" className="px-2.5 py-2 text-left">Name</th>
            <th scope="col" className="px-2.5 py-2 text-left">Status</th>
            <th scope="col" className="px-2.5 py-2 text-left">Uploaded</th>
            <th scope="col" className="px-2.5 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const isSelected = selectedIds.has(document.id);
            return (
              <tr
                key={document.id}
                className={clsx(
                  "border-b border-slate-200 last:border-b-0 transition-colors hover:bg-slate-50",
                  isSelected ? "bg-brand-50/50" : "bg-white"
                )}
              >
                <td className="px-2.5 py-2 align-middle">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    checked={isSelected}
                    onChange={() => onToggleDocument(document.id)}
                    disabled={disableSelection}
                  />
                </td>
                <td className="px-2.5 py-2 align-middle">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-slate-900" title={document.name}>{document.name}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
                      <span className="truncate">{formatFileDescription(document)}</span>
                      {renderJobStatus ? <span className="truncate">{renderJobStatus(document)}</span> : null}
                    </div>
                  </div>
                </td>
                <td className="px-2.5 py-2 align-middle">
                  <span className={clsx(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                    statusBadgeClass(document.status)
                  )}>
                    {formatStatusLabel ? formatStatusLabel(document.status) : document.status}
                  </span>
                </td>
                <td className="px-2.5 py-2 align-middle">
                  <time
                    dateTime={document.created_at}
                    className="block truncate text-xs text-slate-600"
                    title={uploadedFormatter.format(new Date(document.created_at))}
                  >
                    {formatUploadedAt(document)}
                  </time>
                </td>
                <td className="px-2.5 py-2 align-middle text-right">
                  <DocumentActionsMenu
                    document={document}
                    onDownload={onDownloadDocument}
                    onDelete={onDeleteDocument}
                    onRun={onRunDocument}
                    disabled={disableRowActions}
                    downloading={downloadingId === document.id}
                    safeModeEnabled={safeModeEnabled}
                    safeModeMessage={safeModeMessage}
                    safeModeLoading={safeModeLoading}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------- Row actions ------------------------------- */

interface DocumentActionsMenuProps {
  readonly document: DocumentRecord;
  readonly onDownload?: (document: DocumentRecord) => void;
  readonly onDelete?: (document: DocumentRecord) => void;
  readonly onRun?: (document: DocumentRecord) => void;
  readonly disabled?: boolean;
  readonly downloading?: boolean;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function DocumentActionsMenu({
  document,
  onDownload,
  onDelete,
  onRun,
  disabled = false,
  downloading = false,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DocumentActionsMenuProps) {
  const runDisabled = disabled || !onRun || safeModeEnabled || safeModeLoading;
  const runTitle = safeModeEnabled
    ? safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : undefined;

  return (
    <div className="inline-flex items-center gap-1.5">
      <Button
        type="button"
        size="sm"
        variant="primary"
        onClick={() => {
          if (runDisabled) return;
          onRun?.(document);
        }}
        disabled={runDisabled}
        title={runTitle}
      >
        Run
      </Button>

      <button
        type="button"
        onClick={() => onDownload?.(document)}
        className={clsx(
          "px-2 py-1 text-xs font-medium text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
          downloading && "opacity-60"
        )}
        disabled={disabled || downloading}
      >
        {downloading ? "Downloading…" : "Download"}
      </button>

      <button
        type="button"
        onClick={() => onDelete?.(document)}
        className="px-2 py-1 text-xs font-semibold text-danger-600 hover:text-danger-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500"
        disabled={disabled}
      >
        Delete
      </button>
    </div>
  );
}

/* --------------------------- Formatting helpers --------------------------- */

function formatFileDescription(document: DocumentRecord) {
  const parts: string[] = [];
  if (document.content_type) parts.push(humanizeContentType(document.content_type));
  if (typeof document.byte_size === "number" && document.byte_size >= 0) parts.push(formatFileSize(document.byte_size));
  return parts.join(" • ") || "Unknown type";
}

function humanizeContentType(contentType: string) {
  const mapping: Record<string, string> = {
    "application/pdf": "PDF document",
    "text/csv": "CSV file",
    "text/tab-separated-values": "TSV file",
    "application/vnd.ms-excel": "Excel spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel spreadsheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12": "Excel macro spreadsheet",
  };
  return mapping[contentType] ?? contentType;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const formatted = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${formatted} ${units[unitIndex]}`;
}

function statusBadgeClass(status: DocumentRecord["status"]) {
  switch (status) {
    case "processed":
      return "bg-success-100 text-success-700";
    case "processing":
      return "bg-warning-100 text-warning-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "archived":
      return "bg-slate-200 text-slate-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function formatUploadedAt(document: DocumentRecord) {
  return uploadedFormatter.format(new Date(document.created_at));
}
/* --------------------------------- Run Drawer --------------------------------- */

interface RunExtractionDrawerProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord | null;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function RunExtractionDrawer({
  open,
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: RunExtractionDrawerProps) {
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (open) {
      previouslyFocusedElementRef.current =
        window.document.activeElement instanceof HTMLElement ? window.document.activeElement : null;
    } else {
      previouslyFocusedElementRef.current?.focus();
      previouslyFocusedElementRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    const originalOverflow = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    return () => {
      window.document.body.style.overflow = originalOverflow;
    };
  }, [open]);

  if (typeof window === "undefined" || !open || !documentRecord) return null;

  return createPortal(
    <RunExtractionDrawerContent
      workspaceId={workspaceId}
      documentRecord={documentRecord}
      onClose={onClose}
      onRunSuccess={onRunSuccess}
      onRunError={onRunError}
      safeModeEnabled={safeModeEnabled}
      safeModeMessage={safeModeMessage}
      safeModeLoading={safeModeLoading}
    />,
    window.document.body,
  );
}

interface DrawerContentProps {
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function RunExtractionDrawerContent({
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DrawerContentProps) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();
  const configsQuery = useConfigsQuery({ workspaceId });
  const submitJob = useSubmitJob(workspaceId);
  const { preferences, setPreferences } = useDocumentRunPreferences(
    workspaceId,
    documentRecord.id,
  );

  const allConfigs = useMemo(() => configsQuery.data?.items ?? [], [configsQuery.data]);
  const selectableConfigs = useMemo(
    () => allConfigs.filter((config) => !config.deleted_at && config.active_version),
    [allConfigs],
  );

  const preferredSelection = useMemo(() => {
    if (preferences.configId) {
      const match = selectableConfigs.find((config) => config.config_id === preferences.configId);
      if (match) {
        return {
          configId: match.config_id,
          versionId: preferences.configVersionId ?? match.active_version?.config_version_id ?? null,
        } as const;
      }
    }
    const fallback = selectableConfigs[0];
    return {
      configId: fallback?.config_id ?? "",
      versionId: fallback?.active_version?.config_version_id ?? null,
    } as const;
  }, [preferences.configId, preferences.configVersionId, selectableConfigs]);

  const [selectedConfigId, setSelectedConfigId] = useState<string>(preferredSelection.configId);
  const [selectedVersionId, setSelectedVersionId] = useState<string>(preferredSelection.versionId ?? "");

  useEffect(() => {
    setSelectedConfigId(preferredSelection.configId);
    setSelectedVersionId(preferredSelection.versionId ?? "");
  }, [preferredSelection]);

  const selectedConfig = useMemo(
    () => selectableConfigs.find((config) => config.config_id === selectedConfigId) ?? null,
    [selectableConfigs, selectedConfigId],
  );
  const selectedActiveVersion = selectedConfig?.active_version ?? null;

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const safeModeDetail = safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const focusable = getFocusableElements(dialog);
    (focusable[0] ?? dialog).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusableElements = getFocusableElements(dialog);
      if (focusableElements.length === 0) {
        event.preventDefault();
        return;
      }
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = window.document.activeElement;

      if (event.shiftKey) {
        if (!dialog.contains(activeElement) || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
        return;
      }

      if (activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    dialog.addEventListener("keydown", handleKeyDown);
    return () => dialog.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const hasConfigurations = selectableConfigs.length > 0;
  const runDisabled =
    submitJob.isPending || safeModeLoading || safeModeEnabled || !hasConfigurations || !selectedVersionId;
  const runButtonTitle = safeModeEnabled
    ? safeModeDetail
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : undefined;

  const handleSubmit = () => {
    if (safeModeEnabled || safeModeLoading) {
      return;
    }
    if (!selectedConfig || !selectedActiveVersion || !selectedVersionId) {
      setErrorMessage("Select a configuration before running the extractor.");
      return;
    }
    setErrorMessage(null);
    submitJob.mutate(
      {
        input_document_id: documentRecord.id,
        config_version_id: selectedVersionId,
      },
      {
        onSuccess: (job) => {
          setPreferences({ configId: selectedConfig.config_id, configVersionId: selectedVersionId });
          onRunSuccess?.(job);
          onClose();
        },
        onError: (error) => {
          const message = error instanceof Error ? error.message : "Unable to submit extraction job.";
          setErrorMessage(message);
          onRunError?.(message);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className="flex-1 bg-slate-900/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="relative flex h-full w-[min(28rem,92vw)] flex-col border-l border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">Run extraction</h2>
            <p id={descriptionId} className="text-xs text-slate-500">Prepare and submit a processing job.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitJob.isPending}>
            Close
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-sm text-slate-600">
          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Document</p>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-800" title={documentRecord.name}>{documentRecord.name}</p>
              <p className="text-xs text-slate-500">Uploaded {new Date(documentRecord.created_at).toLocaleString()}</p>
              {documentRecord.last_run_at ? (
                <p className="text-xs text-slate-500">
                  Last run {new Date(documentRecord.last_run_at).toLocaleString()}
                </p>
              ) : null}
            </div>
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Configuration</p>
            {configsQuery.isLoading ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Loading configurations…
              </div>
            ) : configsQuery.isError ? (
              <Alert tone="danger">
                Unable to load configurations.{" "}
                {configsQuery.error instanceof Error ? configsQuery.error.message : "Try again later."}
              </Alert>
            ) : hasConfigurations ? (
              <Select
                value={selectedConfigId}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelectedConfigId(value);
                  const target = selectableConfigs.find((config) => config.config_id === value) ?? null;
                  const versionId = target?.active_version?.config_version_id ?? "";
                  setSelectedVersionId(versionId);
                  if (target && versionId) {
                    setPreferences({ configId: target.config_id, configVersionId: versionId });
                  }
                }}
                disabled={submitJob.isPending}
              >
                <option value="">Select configuration</option>
                {selectableConfigs.map((config) => (
                  <option key={config.config_id} value={config.config_id}>
                    {config.title} (Active v{config.active_version?.semver ?? "–"})
                  </option>
                ))}
              </Select>
            ) : (
              <Alert tone="info">No configurations available. Create one before running extraction.</Alert>
            )}
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Advanced options</p>
            <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Sheet selection and advanced flags will appear here once the processor supports them.
            </p>
          </section>

          {safeModeEnabled ? <Alert tone="warning">{safeModeDetail}</Alert> : null}
          {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitJob.isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            isLoading={submitJob.isPending}
            disabled={runDisabled}
            title={runButtonTitle}
          >
            Run extraction
          </Button>
        </footer>
      </aside>
    </div>
  );
}
/* ------------------------ Global drag & drop overlay ------------------------ */

function DropAnywhereOverlay({
  onFiles,
  disabled,
  workspaceName,
}: {
  onFiles: (files: File[]) => void | Promise<void>;
  disabled?: boolean;
  workspaceName?: string;
}) {
  const [active, setActive] = useState(false);
  const counterRef = useRef(0);

  useEffect(() => {
    if (disabled) return;

    const onDragEnter = (e: DragEvent) => {
      if (!e.dataTransfer || ![...e.dataTransfer.types].includes("Files")) return;
      counterRef.current += 1;
      setActive(true);
    };
    const onDragOver = (e: DragEvent) => {
      if (!active) return;
      e.preventDefault();
    };
    const onDragLeave = () => {
      counterRef.current = Math.max(0, counterRef.current - 1);
      if (counterRef.current === 0) setActive(false);
    };
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      setActive(false);
      counterRef.current = 0;
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length) void onFiles(files);
    };

    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, [active, disabled, onFiles]);

  return (
    <div
      aria-hidden={!active}
      className={clsx(
        "pointer-events-none fixed inset-0 z-[60] transition",
        active ? "opacity-100" : "opacity-0"
      )}
    >
      <div className="absolute inset-0 bg-slate-900/25 backdrop-blur-[2px]" />
      <div className="absolute inset-0 flex items-center justify-center p-6">
        <div className="pointer-events-none rounded-2xl border border-white/70 bg-white/90 px-6 py-5 shadow-2xl">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-white shadow">
              <svg viewBox="0 0 24 24" className="h-5 w-5 text-slate-700" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <div className="text-center sm:text-left">
              <p className="text-base font-semibold text-slate-900">Drop to upload</p>
              <p className="text-sm text-slate-600">
                Files will upload to <span className="font-medium">{workspaceName ?? "this workspace"}</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------- UI helpers -------------------------------- */

function SkeletonList() {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <div className="h-4 w-4 rounded bg-slate-100" />
          <div className="h-4 flex-1 rounded bg-slate-100" />
          <div className="h-4 w-24 rounded bg-slate-100" />
          <div className="h-4 w-40 rounded bg-slate-100" />
          <div className="h-8 w-40 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

function BulkBar({
  count,
  onClear,
  onRun,
  onDelete,
  busy,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: {
  count: number;
  onClear: () => void;
  onRun: () => void;
  onDelete: () => void;
  busy?: boolean;
  safeModeEnabled?: boolean;
  safeModeMessage?: string;
  safeModeLoading?: boolean;
}) {
  if (count === 0) return null;
  const runDisabled = busy || safeModeEnabled || safeModeLoading;
  const runTitle = safeModeEnabled
    ? safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : undefined;
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 mx-auto max-w-7xl px-2 pb-2 sm:px-4 sm:pb-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 p-3 text-sm text-slate-700 shadow-lg backdrop-blur">
        <span className="mr-2"><strong>{count}</strong> selected</span>
        <Button variant="ghost" size="sm" onClick={onClear}>Clear</Button>
        <Button size="sm" onClick={() => !runDisabled && onRun()} disabled={runDisabled} title={runTitle}>
          Run extraction
        </Button>
        <Button size="sm" variant="danger" onClick={onDelete} disabled={busy} isLoading={busy}>Delete</Button>
      </div>
    </div>
  );
}

function EmptyState({ onUploadClick }: { onUploadClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-50">
        <svg className="h-6 w-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-base font-semibold text-slate-900">No documents yet</p>
      <p className="max-w-md text-sm text-slate-600">Tap Upload or drag files anywhere in the window.</p>
      <Button onClick={onUploadClick} className="w-full sm:w-auto">Upload</Button>
    </div>
  );
}

/* ------------------------------ Job status chip ------------------------------ */

function DocumentJobStatus({ workspaceId, documentId }: { workspaceId: string; documentId: string }) {
  const jobsQuery = useDocumentJobs(workspaceId, documentId, { limit: 3 });

  if (jobsQuery.isLoading) return <span className="text-xs text-slate-400">Loading runs…</span>;
  if (jobsQuery.isError) {
    return (
      <span className="text-xs text-rose-600">
        {jobsQuery.error instanceof Error ? jobsQuery.error.message : "Unable to load runs."}
      </span>
    );
  }

  const jobs = jobsQuery.data ?? [];
  if (jobs.length === 0) return <span className="text-xs text-slate-400">No runs yet</span>;

  const latestJob = jobs[0];
  const remaining = jobs.length - 1;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={clsx(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
          jobStatusBadgeClass(latestJob.status),
        )}
      >
        {formatJobStatus(latestJob.status)}
        <span className="ml-1 font-normal text-slate-500">{formatRelativeTime(latestJob.updated_at)}</span>
      </span>
      {remaining > 0 ? <span className="text-[11px] text-slate-400">+{remaining} more</span> : null}
    </div>
  );
}

function jobStatusBadgeClass(status: JobStatus) {
  switch (status) {
    case "succeeded":
      return "bg-success-100 text-success-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "running":
      return "bg-brand-100 text-brand-700";
    default:
      return "bg-slate-200 text-slate-700";
  }
}

function formatJobStatus(status: JobStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const diffMs = date.getTime() - Date.now();
  const diffSeconds = Math.round(diffMs / 1000);
  const absSeconds = Math.abs(diffSeconds);
  if (absSeconds < 60) return relativeTimeFormatter.format(diffSeconds, "second");
  const diffMinutes = Math.round(diffSeconds / 60);
  const absMinutes = Math.abs(diffMinutes);
  if (absMinutes < 60) return relativeTimeFormatter.format(diffMinutes, "minute");
  const diffHours = Math.round(diffMinutes / 60);
  const absHours = Math.abs(diffHours);
  if (absHours < 24) return relativeTimeFormatter.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 30) return relativeTimeFormatter.format(diffDays, "day");
  const diffMonths = Math.round(diffDays / 30);
  if (Math.abs(diffMonths) < 12) return relativeTimeFormatter.format(diffMonths, "month");
  const diffYears = Math.round(diffDays / 365);
  return relativeTimeFormatter.format(diffYears, "year");
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function getFocusableElements(container: HTMLElement) {
  const selectors = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ];
  return Array.from(container.querySelectorAll<HTMLElement>(selectors.join(','))).filter(
    (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true',
  );
}
