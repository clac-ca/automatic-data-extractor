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

import { useNavigate } from "@app/nav/history";
import { useSearchParams } from "@app/nav/urlState";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useSession } from "@shared/auth/context/SessionContext";
import { useConfigurationsQuery } from "@shared/configurations";
import { client } from "@shared/api/client";
import { ApiError } from "@shared/api/errors";
import { useFlattenedPages } from "@shared/api/pagination";
import { createScopedStorage } from "@shared/storage";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import type { components, paths, RunSummary } from "@schema";
import {
  fetchDocumentSheets,
  fetchTagCatalog,
  replaceDocumentTags,
  uploadWorkspaceDocument,
  type DocumentSheet,
} from "@shared/documents";
import { useUploadQueue, type UploadQueueItem, type UploadQueueSummary } from "@shared/uploads/queue";
import type { UploadProgress } from "@shared/uploads/xhr";
import { RunSummaryView, TelemetrySummary } from "@shared/runs/RunInsights";
import {
  createRun,
  fetchRun,
  fetchRunTelemetry,
  runLogsUrl,
  runOutputUrl,
  runQueryKeys,
  type RunResource,
  type RunStatus,
} from "@shared/runs/api";
import type { RunStreamEvent } from "@shared/runs/types";

import { Alert } from "@ui/Alert";
import { Select } from "@ui/Select";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

/* -------------------------------- Types & constants ------------------------------- */

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];
type RunSubmissionOptions = components["schemas"]["RunCreateOptionsBase"];
type RunSubmissionPayload = {
  readonly configId: components["schemas"]["RunWorkspaceCreateRequest"]["configuration_id"];
  readonly documentId: string;
  readonly options: RunSubmissionOptions;
};
type RunBatchCreateOptions = components["schemas"]["RunBatchCreateOptions"];
type RunBatchCreateRequest = components["schemas"]["RunWorkspaceBatchCreateRequest"];
type RunBatchSubmissionPayload = {
  readonly configId: RunBatchCreateRequest["configuration_id"];
  readonly documentIds: readonly string[];
  readonly options?: RunBatchCreateOptions;
};
type DocumentListPage = components["schemas"]["DocumentPage"];
type UploadItem = UploadQueueItem<DocumentRecord>;
type UploadRunState = {
  readonly status: "pending" | "queued" | "failed";
  readonly runId?: string;
  readonly error?: string;
};
type DocumentTableRow = {
  readonly key: string;
  readonly document?: DocumentRecord;
  readonly upload?: UploadItem;
  readonly runState?: UploadRunState;
};

type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

type DocumentsView = "mine" | "team" | "attention" | "recent";

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

const SORT_OPTIONS = [
  "-created_at",
  "created_at",
  "-last_run_at",
  "last_run_at",
  "-byte_size",
  "byte_size",
  "name",
  "-name",
  "status",
  "-status",
  "source",
  "-source",
] as const;
type SortOption = (typeof SORT_OPTIONS)[number];

const DEFAULT_VIEW: DocumentsView = "mine";
const DOCUMENT_VIEW_PRESETS: Record<
  DocumentsView,
  {
    readonly label: string;
    readonly description: string;
    readonly presetStatuses?: readonly DocumentStatus[];
    readonly presetSort?: SortOption;
    readonly uploader?: "me" | null;
  }
> = {
  mine: {
    label: "My uploads",
    description: "Documents you uploaded",
    uploader: "me",
  },
  team: {
    label: "All documents",
    description: "Everything in this workspace",
  },
  attention: {
    label: "Needs attention",
    description: "Failed or processing files",
    presetStatuses: ["failed", "processing"],
  },
  recent: {
    label: "Recently run",
    description: "Latest run activity",
    presetSort: "-last_run_at",
  },
};

function parseView(value: string | null): DocumentsView {
  if (!value) return DEFAULT_VIEW;
  return (Object.keys(DOCUMENT_VIEW_PRESETS) as DocumentsView[]).includes(value as DocumentsView)
    ? (value as DocumentsView)
    : DEFAULT_VIEW;
}

function parseStatusParam(value: string | null): Set<DocumentStatus> {
  if (!value) return new Set();
  const tokens = value
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean) as DocumentStatus[];
  const valid = tokens.filter((token): token is DocumentStatus =>
    ["uploaded", "processing", "processed", "failed", "archived"].includes(token),
  );
  return new Set(valid);
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
  list: (
    workspaceId: string,
    sort: string | null,
    uploader: string | null,
  ) => [...documentsKeys.workspace(workspaceId), "list", { sort, uploader }] as const,
};

const DOCUMENTS_PAGE_SIZE = 50;
const MAX_DOCUMENT_TAGS = 50;
/* -------------------------------- Route component -------------------------------- */

export default function WorkspaceDocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const session = useSession();
  const queryClient = useQueryClient();

  // URL-synced state
  const [searchParams, setSearchParams] = useSearchParams();
  const setSearchParamsRef = useRef(setSearchParams);
  useEffect(() => {
    setSearchParamsRef.current = setSearchParams;
  }, [setSearchParams]);
  const initialViewFromParams = parseView(searchParams.get("view"));
  const [viewFilter, setViewFilter] = useState<DocumentsView>(initialViewFromParams);
  const [statusFilters, setStatusFilters] = useState<Set<DocumentStatus>>(() => {
    const statusParam = searchParams.get("status");
    if (statusParam) return parseStatusParam(statusParam);
    const preset = DOCUMENT_VIEW_PRESETS[initialViewFromParams].presetStatuses ?? [];
    return new Set(preset);
  });
  const [sortOrder, setSortOrder] = useState<SortOption>(() => {
    const sortParam = searchParams.get("sort");
    if (sortParam) return parseSort(sortParam);
    const presetSort = DOCUMENT_VIEW_PRESETS[initialViewFromParams].presetSort;
    return presetSort ?? "-created_at";
  });
  const [searchTerm, setSearchTerm] = useState(searchParams.get("q") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(searchTerm.trim());
  const statusFiltersArray = useMemo(() => Array.from(statusFilters), [statusFilters]);
  const viewPreset = DOCUMENT_VIEW_PRESETS[viewFilter];
  const uploaderFilter = viewPreset.uploader ?? null;

  // File input + selection
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const selectedIdsSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedIdsArray = useMemo(() => Array.from(selectedIdsSet), [selectedIdsSet]);
  const selectedCount = selectedIdsSet.size;
  const currentUserLabel = session.user.name ?? session.user.email ?? "You";

  // Operations
  const startUpload = useCallback(
    (file: File, { onProgress }: { onProgress: (progress: UploadProgress) => void }) =>
      uploadWorkspaceDocument(workspace.id, file, { onProgress }),
    [workspace.id],
  );
  const uploadQueue = useUploadQueue<DocumentRecord>({
    concurrency: 3,
    startUpload,
  });
  const uploadSummary = uploadQueue.summary;
  const uploadBusy = uploadSummary.inFlightCount > 0;
  const deleteDocuments = useDeleteWorkspaceDocuments(workspace.id);
  const safeModeStatus = useSafeModeStatus();
  const safeModeEnabled = safeModeStatus.data?.enabled ?? false;
  const safeModeDetail = safeModeStatus.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const safeModeLoading = safeModeStatus.isPending;

  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const allConfigurations = useMemo(
    () => configurationsQuery.data?.items ?? [],
    [configurationsQuery.data],
  );
  const { selectableConfigs, activeConfig } = useMemo(
    () => resolveSelectableConfigs(allConfigurations),
    [allConfigurations],
  );
  const preferredConfigId = useMemo(() => {
    if (activeConfig?.id) {
      return activeConfig.id;
    }
    return selectableConfigs[0]?.id ?? "";
  }, [activeConfig?.id, selectableConfigs]);

  const [banner, setBanner] = useState<{ tone: "error"; message: string } | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [runDrawerDocument, setRunDrawerDocument] = useState<DocumentRecord | null>(null);
  const [runDrawerRunId, setRunDrawerRunId] = useState<string | null>(null);
  const [batchRunOpen, setBatchRunOpen] = useState(false);

  const [runOnUploadEnabled, setRunOnUploadEnabled] = useState(false);
  const [runOnUploadConfigId, setRunOnUploadConfigId] = useState("");
  const [runOnUploadStates, setRunOnUploadStates] = useState<Record<string, UploadRunState>>({});
  const runOnUploadHandledRef = useRef(new Set<string>());
  const uploadRefreshHandledRef = useRef(new Set<string>());

  const isDeleting = deleteDocuments.isPending;
  const runOnUploadAvailable =
    runOnUploadEnabled && Boolean(runOnUploadConfigId) && !safeModeEnabled;

  useEffect(() => {
    setRunOnUploadConfigId((current) => {
      if (current && selectableConfigs.some((config) => config.id === current)) {
        return current;
      }
      return preferredConfigId;
    });
  }, [preferredConfigId, selectableConfigs]);

  useEffect(() => {
    if (runOnUploadEnabled && (!runOnUploadConfigId || safeModeEnabled)) {
      setRunOnUploadEnabled(false);
    }
  }, [runOnUploadConfigId, runOnUploadEnabled, safeModeEnabled]);

  // Query
  const documentsQuery = useWorkspaceDocuments(workspace.id, {
    statuses: statusFiltersArray,
    search: debouncedSearch,
    sort: sortOrder,
    uploader: uploaderFilter,
  });
  const { refetch: refetchDocuments } = documentsQuery;
  const getDocumentKey = useCallback((document: DocumentRecord) => document.id, []);
  const documentsRaw = useFlattenedPages(documentsQuery.data?.pages, getDocumentKey);
  const documentsFiltered = useMemo(() => {
    const normalizedSearch = debouncedSearch.toLowerCase();
    const uploaderId = uploaderFilter === "me" ? session.user.id : null;
    const uploaderEmail = uploaderFilter === "me" ? session.user.email ?? null : null;
    return documentsRaw.filter((doc) => {
      if (statusFiltersArray.length > 0 && !statusFiltersArray.includes(doc.status)) {
        return false;
      }
      if (uploaderFilter === "me") {
        const docUploaderId = (doc as { uploader_id?: string | null }).uploader_id ?? doc.uploader?.id ?? null;
        const docUploaderEmail = doc.uploader?.email ?? null;
        if (uploaderId && docUploaderId && docUploaderId !== uploaderId) {
          return false;
        }
        if (!docUploaderId && uploaderEmail && docUploaderEmail && docUploaderEmail !== uploaderEmail) {
          return false;
        }
      }
      if (normalizedSearch) {
        const haystack = `${doc.name ?? ""} ${(doc as { source?: string | null }).source ?? ""}`.toLowerCase();
        if (!haystack.includes(normalizedSearch)) {
          return false;
        }
      }
      return true;
    });
  }, [debouncedSearch, documentsRaw, session.user.email, session.user.id, statusFiltersArray, uploaderFilter]);
  const documentsById = useMemo(() => {
    const map = new Map(documentsRaw.map((document) => [document.id, document]));
    for (const item of uploadQueue.items) {
      const document = item.response;
      if (document?.id) {
        map.set(document.id, document);
      }
    }
    return map;
  }, [documentsRaw, uploadQueue.items]);
  const uploadRows = useMemo<DocumentTableRow[]>(() => {
    return uploadQueue.items.map((item) => {
      const documentId = item.response?.id;
      const document = documentId ? documentsById.get(documentId) ?? item.response : item.response;
      return {
        key: item.id,
        upload: item,
        document,
        runState: runOnUploadStates[item.id],
      };
    });
  }, [documentsById, runOnUploadStates, uploadQueue.items]);
  const uploadDocumentIds = useMemo(() => {
    const ids = new Set<string>();
    for (const row of uploadRows) {
      if (row.document?.id) {
        ids.add(row.document.id);
      }
    }
    return ids;
  }, [uploadRows]);
  const documentRows = useMemo<DocumentTableRow[]>(
    () =>
      documentsFiltered
        .filter((document) => !uploadDocumentIds.has(document.id))
        .map((document) => ({ key: document.id, document })),
    [documentsFiltered, uploadDocumentIds],
  );
  const tableRows = useMemo(() => [...uploadRows, ...documentRows], [uploadRows, documentRows]);
  const selectableDocumentIds = useMemo(
    () => tableRows.flatMap((row) => (row.document ? [row.document.id] : [])),
    [tableRows],
  );
  const selectableDocumentIdSet = useMemo(
    () => new Set(selectableDocumentIds),
    [selectableDocumentIds],
  );
  const fetchingNextPage = documentsQuery.isFetchingNextPage;
  const backgroundFetch = documentsQuery.isFetching && !fetchingNextPage;
  const totalDocuments = documentsFiltered.length;

  useEffect(() => {
    let shouldInvalidate = false;
    for (const item of uploadQueue.items) {
      if (item.status !== "succeeded" || !item.response?.id) {
        continue;
      }
      if (uploadRefreshHandledRef.current.has(item.id)) {
        continue;
      }
      uploadRefreshHandledRef.current.add(item.id);
      shouldInvalidate = true;
    }
    if (shouldInvalidate) {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspace.id) });
    }
  }, [queryClient, uploadQueue.items, workspace.id]);

  useEffect(() => {
    if (!uploadQueue.items.length || safeModeLoading) {
      return;
    }

    for (const item of uploadQueue.items) {
      if (item.status !== "succeeded") {
        continue;
      }
      if (runOnUploadHandledRef.current.has(item.id)) {
        continue;
      }
      runOnUploadHandledRef.current.add(item.id);

      if (!runOnUploadAvailable) {
        continue;
      }

      const documentId = item.response?.id;
      if (!documentId) {
        setRunOnUploadStates((current) => ({
          ...current,
          [item.id]: { status: "failed", error: "Upload response missing document metadata." },
        }));
        continue;
      }

      setRunOnUploadStates((current) => ({
        ...current,
        [item.id]: { status: "pending" },
      }));

      createRun(workspace.id, {
        input_document_id: documentId,
        configuration_id: runOnUploadConfigId ?? undefined,
      })
        .then((run) => {
          setRunOnUploadStates((current) => ({
            ...current,
            [item.id]: { status: "queued", runId: run.id },
          }));
        })
        .catch((error) => {
          const message = resolveApiErrorMessage(error, "Unable to queue a run for this upload.");
          setRunOnUploadStates((current) => ({
            ...current,
            [item.id]: { status: "failed", error: message },
          }));
        });
    }
  }, [runOnUploadAvailable, runOnUploadConfigId, safeModeLoading, uploadQueue.items, workspace.id]);

  /* ----------------------------- URL sync ----------------------------- */
  useEffect(() => {
    const paramValue = searchParams.get("q") ?? "";
    setSearchTerm((current) => (current === paramValue ? current : paramValue));
    const normalized = paramValue.trim();
    setDebouncedSearch((current) => (current === normalized ? current : normalized));
  }, [searchParams]);

  useEffect(() => {
    const s = new URLSearchParams();
    if (statusFilters.size > 0) s.set("status", Array.from(statusFilters).join(","));
    if (sortOrder !== "-created_at") s.set("sort", sortOrder);
    if (debouncedSearch) s.set("q", debouncedSearch);
    if (viewFilter !== DEFAULT_VIEW) s.set("view", viewFilter);
    setSearchParamsRef.current(s, { replace: true });
  }, [statusFilters, sortOrder, debouncedSearch, viewFilter]);

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
      let changed = false;
      for (const id of current) {
        if (selectableDocumentIdSet.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [selectableDocumentIdSet]);

  const handleSelectView = useCallback((nextView: DocumentsView) => {
    const preset = DOCUMENT_VIEW_PRESETS[nextView];
    setViewFilter(nextView);
    setStatusFilters(new Set(preset.presetStatuses ?? []));
    setSortOrder(preset.presetSort ?? "-created_at");
    setSearchTerm("");
    setDebouncedSearch("");
  }, []);

  const toggleStatusFilter = useCallback((status: DocumentStatus) => {
    setStatusFilters((current) => {
      const next = new Set(current);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }, []);

  const clearStatusFilters = useCallback(() => {
    setStatusFilters(new Set());
  }, []);

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

  const renderRunStatus = useCallback((documentItem: DocumentRecord) => <DocumentRunStatus document={documentItem} />, []);

  const handleOpenFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUploadFiles = useCallback(
    (files: readonly File[]) => {
      if (!files.length) return;
      setBanner(null);
      uploadQueue.enqueue(files);
    },
    [uploadQueue],
  );

  const handleCancelUpload = useCallback(
    (itemId: string) => {
      uploadQueue.cancel(itemId);
    },
    [uploadQueue],
  );

  const handleRetryUpload = useCallback(
    (itemId: string) => {
      uploadQueue.retry(itemId);
      setRunOnUploadStates((current) => {
        if (!(itemId in current)) {
          return current;
        }
        const next = { ...current };
        delete next[itemId];
        return next;
      });
      runOnUploadHandledRef.current.delete(itemId);
      uploadRefreshHandledRef.current.delete(itemId);
    },
    [uploadQueue],
  );

  const handleRemoveUpload = useCallback(
    (itemId: string) => {
      uploadQueue.remove(itemId);
      setRunOnUploadStates((current) => {
        if (!(itemId in current)) {
          return current;
        }
        const next = { ...current };
        delete next[itemId];
        return next;
      });
      runOnUploadHandledRef.current.delete(itemId);
      uploadRefreshHandledRef.current.delete(itemId);
    },
    [uploadQueue],
  );

  const handleClearCompletedUploads = useCallback(() => {
    const completed = uploadQueue.items.filter((item) => isTerminalUploadStatus(item.status));
    if (!completed.length) return;
    uploadQueue.clearCompleted();
    setRunOnUploadStates((current) => {
      const next = { ...current };
      for (const item of completed) {
        delete next[item.id];
      }
      return next;
    });
    for (const item of completed) {
      runOnUploadHandledRef.current.delete(item.id);
      uploadRefreshHandledRef.current.delete(item.id);
    }
  }, [uploadQueue]);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    handleUploadFiles(files);
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
      if (selectableDocumentIds.length === 0) return new Set();
      if (
        current.size === selectableDocumentIds.length &&
        selectableDocumentIds.every((id) => current.has(id))
      ) {
        return new Set();
      }
      return new Set(selectableDocumentIds);
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

  const handleOpenRunDrawer = useCallback((document: DocumentRecord, runId?: string | null) => {
    setRunDrawerDocument(document);
    setRunDrawerRunId(runId ?? null);
  }, []);

  const handleRunSuccess = useCallback(() => {
    void refetchDocuments();
  }, [refetchDocuments]);

  const handleRunError = useCallback((message: string) => {
    setBanner({ tone: "error", message });
  }, []);

  const onResetFilters = () => {
    setViewFilter(DEFAULT_VIEW);
    setSearchTerm("");
    setDebouncedSearch("");
    setStatusFilters(new Set());
    setSortOrder("-created_at");
  };

  const isDefaultFilters =
    viewFilter === DEFAULT_VIEW && statusFilters.size === 0 && sortOrder === "-created_at" && !debouncedSearch;

  /* -------------------------------- Render -------------------------------- */

  return (
    <>
      {/* Global drop-anywhere overlay */}
      <DropAnywhereOverlay
        workspaceName={workspace.name ?? undefined}
        disabled={false}
        onFiles={handleUploadFiles}
      />

      <div className="space-y-3">
        {/* Hidden file input (paired with Upload) */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        <DocumentsHeader
          workspaceName={workspace.name}
          totalDocuments={totalDocuments}
          view={viewFilter}
          onChangeView={handleSelectView}
          sort={sortOrder}
          onSort={setSortOrder}
          onReset={onResetFilters}
          isFetching={documentsQuery.isFetching}
          isDefault={isDefaultFilters}
          onUploadClick={handleOpenFilePicker}
          uploadDisabled={false}
          uploadLoading={uploadBusy}
          selectedStatuses={statusFilters}
          onToggleStatus={toggleStatusFilter}
          onClearStatuses={clearStatusFilters}
          runOnUploadEnabled={runOnUploadEnabled}
          runOnUploadConfigId={runOnUploadConfigId}
          uploadSummary={uploadSummary}
          configurations={selectableConfigs}
          configurationsLoading={configurationsQuery.isLoading}
          configurationsError={configurationsQuery.isError}
          configurationsErrorMessage={
            configurationsQuery.error instanceof Error ? configurationsQuery.error.message : undefined
          }
          onToggleRunOnUpload={() => setRunOnUploadEnabled((current) => !current)}
          onSelectRunOnUploadConfig={setRunOnUploadConfigId}
          onClearCompletedUploads={handleClearCompletedUploads}
          safeModeEnabled={safeModeEnabled}
          safeModeMessage={safeModeDetail}
          safeModeLoading={safeModeLoading}
        />

        {banner ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
            {banner.message}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white text-sm text-slate-700">
          {documentsQuery.isLoading ? (
            <div className="p-4">
              <SkeletonList />
            </div>
          ) : documentsQuery.isError ? (
            <p className="p-4 text-rose-600">Failed to load documents.</p>
          ) : tableRows.length === 0 ? (
            <div className="p-6">
              <EmptyState onUploadClick={handleOpenFilePicker} />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto p-2 sm:p-3">
                <DocumentsTable
                  rows={tableRows}
                  selectedIds={selectedIdsSet}
                  onToggleDocument={handleToggleDocument}
                  onToggleAll={handleToggleAll}
                  disableSelection={backgroundFetch || isDeleting}
                  disableRowActions={deleteDocuments.isPending}
                  formatStatusLabel={statusFormatter}
                  onDeleteDocument={handleDeleteSingle}
                  onDownloadDocument={handleDownloadDocument}
                  onRunDocument={handleOpenRunDrawer}
                  downloadingId={downloadingId}
                  renderRunStatus={renderRunStatus}
                  onViewRun={(document, runId) => handleOpenRunDrawer(document, runId)}
                  onCancelUpload={handleCancelUpload}
                  onRetryUpload={handleRetryUpload}
                  onRemoveUpload={handleRemoveUpload}
                  currentUserLabel={currentUserLabel}
                  safeModeEnabled={safeModeEnabled}
                  safeModeMessage={safeModeDetail}
                  safeModeLoading={safeModeLoading}
                />
              </div>
              {documentsQuery.hasNextPage ? (
                <div className="flex justify-center border-t border-slate-200 bg-slate-50/60 px-3 py-2">
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
          if (!safeModeEnabled && !safeModeLoading) {
            setBatchRunOpen(true);
          }
        }}
        onDelete={handleDeleteSelected}
        busy={isDeleting}
        safeModeEnabled={safeModeEnabled}
        safeModeMessage={safeModeDetail}
        safeModeLoading={safeModeLoading}
      />

      <BatchRunDialog
        open={batchRunOpen}
        workspaceId={workspace.id}
        documentIds={selectedIdsArray}
        documentsById={documentsById}
        configurations={selectableConfigs}
        preferredConfigId={preferredConfigId}
        configurationsLoading={configurationsQuery.isLoading}
        configurationsError={configurationsQuery.isError}
        configurationsErrorMessage={
          configurationsQuery.error instanceof Error ? configurationsQuery.error.message : undefined
        }
        onClose={() => setBatchRunOpen(false)}
        onViewRun={(document, runId) => {
          setBatchRunOpen(false);
          handleOpenRunDrawer(document, runId);
        }}
        safeModeEnabled={safeModeEnabled}
        safeModeMessage={safeModeDetail}
        safeModeLoading={safeModeLoading}
      />

      {/* Run drawer */}
      <RunExtractionDrawer
        open={Boolean(runDrawerDocument)}
        workspaceId={workspace.id}
        documentRecord={runDrawerDocument}
        initialRunId={runDrawerRunId}
        onClose={() => {
          setRunDrawerDocument(null);
          setRunDrawerRunId(null);
        }}
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
  readonly statuses: readonly DocumentStatus[];
  readonly search: string;
  readonly sort: SortOption;
  readonly uploader?: string | null;
}

function useWorkspaceDocuments(workspaceId: string, options: WorkspaceDocumentsOptions) {
  const sort = options.sort.trim() || null;

  return useInfiniteQuery<DocumentListPage>({
    queryKey: documentsKeys.list(workspaceId, sort, options.uploader ?? null),
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

function useSubmitRun(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<RunResource, Error, RunSubmissionPayload>({
    mutationFn: async ({ configId, documentId, options }) => {
      const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/runs", {
        params: { path: { workspace_id: workspaceId } },
        body: {
          input_document_id: documentId,
          configuration_id: configId ?? undefined,
          options,
        },
      });
      if (!data) throw new Error("Expected run payload.");
      return data as RunResource;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useSubmitRunsBatch(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<RunResource[], Error, RunBatchSubmissionPayload>({
    mutationFn: async ({ configId, documentIds, options }) => {
      const baseRunOptions: RunBatchCreateOptions = {
        dry_run: false,
        validate_only: false,
        force_rebuild: false,
        debug: false,
        log_level: "INFO",
      };
      const body: RunBatchCreateRequest = {
        document_ids: [...documentIds],
        configuration_id: configId ?? undefined,
        options: options ?? baseRunOptions,
      };
      const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/runs/batch", {
        params: { path: { workspace_id: workspaceId } },
        body,
      });
      if (!data) {
        throw new Error("Expected batch run payload.");
      }
      return data.runs ?? [];
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
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
          sheetNames: next.sheetNames && next.sheetNames.length > 0 ? [...next.sheetNames] : null,
        },
      });
    },
    [storage, documentId],
  );

  return { preferences, setPreferences } as const;
}

type DocumentRunPreferences = {
  readonly configId: string | null;
  readonly sheetNames: readonly string[] | null;
};
/* ------------------------ API helpers & small utilities ------------------------ */

async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: {
    sort: string | null;
    page: number;
    pageSize: number;
  },
  signal?: AbortSignal,
): Promise<DocumentListPage> {
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

function readRunPreferences(
  storage: ReturnType<typeof createScopedStorage>,
  documentId: string,
): DocumentRunPreferences {
  const all = storage.get<Record<string, DocumentRunPreferences>>();
  if (all && typeof all === "object" && documentId in all) {
    const entry = all[documentId];
    if (entry && typeof entry === "object") {
      const legacySheetNames: string[] = [];
      if ("sheetName" in entry) {
        const sheetNameValue = (entry as { sheetName?: string | null }).sheetName;
        if (typeof sheetNameValue === "string") {
          legacySheetNames.push(sheetNameValue);
        }
      }
      const providedSheetNames = Array.isArray((entry as { sheetNames?: unknown }).sheetNames)
        ? ((entry as { sheetNames?: unknown }).sheetNames as unknown[]).filter(
            (value): value is string => typeof value === "string" && value.length > 0,
          )
        : null;
      const mergedSheetNames = providedSheetNames ?? (legacySheetNames.length > 0 ? legacySheetNames : null);

      return {
        configId: entry.configId ?? null,
        sheetNames: mergedSheetNames,
      };
    }
  }
  return { configId: null, sheetNames: null };
}
/* ---------------------- Command header + filter rail ---------------------- */

function DocumentsHeader({
  workspaceName,
  totalDocuments,
  view,
  onChangeView,
  sort,
  onSort,
  onReset,
  isFetching,
  isDefault,
  onUploadClick,
  uploadDisabled,
  uploadLoading,
  selectedStatuses,
  onToggleStatus,
  onClearStatuses,
  runOnUploadEnabled,
  runOnUploadConfigId,
  uploadSummary,
  configurations,
  configurationsLoading,
  configurationsError,
  configurationsErrorMessage,
  onToggleRunOnUpload,
  onSelectRunOnUploadConfig,
  onClearCompletedUploads,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: {
  workspaceName?: string | null;
  totalDocuments?: number | null;
  view: DocumentsView;
  onChangeView: (view: DocumentsView) => void;
  sort: SortOption;
  onSort: (v: SortOption) => void;
  onReset: () => void;
  isFetching?: boolean;
  isDefault: boolean;
  onUploadClick: () => void;
  uploadDisabled?: boolean;
  uploadLoading?: boolean;
  selectedStatuses: ReadonlySet<DocumentStatus>;
  onToggleStatus: (status: DocumentStatus) => void;
  onClearStatuses: () => void;
  runOnUploadEnabled: boolean;
  runOnUploadConfigId: string;
  uploadSummary: UploadQueueSummary;
  configurations: ConfigurationRecord[];
  configurationsLoading: boolean;
  configurationsError: boolean;
  configurationsErrorMessage?: string;
  onToggleRunOnUpload: () => void;
  onSelectRunOnUploadConfig: (configId: string) => void;
  onClearCompletedUploads: () => void;
  safeModeEnabled?: boolean;
  safeModeMessage?: string;
  safeModeLoading?: boolean;
}) {
  const subtitle =
    typeof totalDocuments === "number"
      ? `${totalDocuments.toLocaleString()} files`
      : workspaceName
        ? `Uploads and runs for ${workspaceName}`
        : "Manage workspace uploads and runs";
  const hasConfigurations = configurations.length > 0;
  const toggleDisabled =
    safeModeEnabled ||
    safeModeLoading ||
    configurationsLoading ||
    configurationsError ||
    !hasConfigurations ||
    !runOnUploadConfigId;
  const disabledReason = safeModeEnabled
    ? safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE
    : safeModeLoading
      ? "Checking safe mode status…"
      : configurationsLoading
        ? "Loading configurations…"
        : configurationsError
          ? configurationsErrorMessage ?? "Unable to load configurations."
          : !hasConfigurations
            ? "Create or activate a configuration to enable run on upload."
            : !runOnUploadConfigId
              ? "Select a configuration to enable run on upload."
              : null;
  const showClearUploads = uploadSummary.completedCount > 0;
  const showUploadSummary = uploadSummary.totalCount > 0;

  return (
    <section
      className="rounded-xl border border-slate-200 bg-white/95 p-3 sm:p-4"
      aria-label="Documents header and filters"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-slate-900 sm:text-xl">
            {workspaceName ? `${workspaceName} documents` : "Documents"}
          </h1>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onReset}
            disabled={isDefault}
            className={clsx(
              "rounded border border-transparent px-3 py-1 text-sm font-medium",
              isDefault
                ? "cursor-default text-slate-300"
                : "text-slate-600 hover:border-slate-200 hover:bg-slate-50 hover:text-slate-900",
            )}
          >
            Reset
          </button>
          <Button
            className="shrink-0"
            onClick={onUploadClick}
            disabled={uploadDisabled}
            isLoading={uploadLoading}
            aria-label="Upload documents"
          >
            Upload
          </Button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
          <span>Run on upload</span>
          <button
            type="button"
            role="switch"
            aria-checked={runOnUploadEnabled}
            onClick={() => {
              if (toggleDisabled) return;
              onToggleRunOnUpload();
            }}
            title={toggleDisabled ? disabledReason ?? undefined : undefined}
            className={clsx(
              "relative h-6 w-11 rounded-full border transition",
              runOnUploadEnabled ? "border-emerald-500 bg-emerald-500" : "border-slate-200 bg-slate-200",
              toggleDisabled && "opacity-60",
            )}
          >
            <span
              className={clsx(
                "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition",
                runOnUploadEnabled ? "left-5" : "left-0.5",
              )}
            />
          </button>
        </label>

        <div className="min-w-[220px]">
          {configurationsLoading ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Loading configurations…
            </div>
          ) : configurationsError ? (
            <Alert tone="danger">
              {configurationsErrorMessage ?? "Unable to load configurations."}
            </Alert>
          ) : hasConfigurations ? (
            <Select
              value={runOnUploadConfigId}
              onChange={(event) => onSelectRunOnUploadConfig(event.target.value)}
              disabled={safeModeEnabled}
            >
              <option value="">Select configuration</option>
              {configurations.map((config) => (
                <option key={config.id} value={config.id}>
                  {formatConfigurationLabel(config)}
                </option>
              ))}
            </Select>
          ) : (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              No configurations available.
            </div>
          )}
        </div>

        {showUploadSummary ? (
          <span className="text-xs text-slate-500">
            {uploadSummary.inFlightCount > 0
              ? `Uploading ${uploadSummary.inFlightCount} file${
                  uploadSummary.inFlightCount === 1 ? "" : "s"
                } · ${uploadSummary.percent}%`
              : `${uploadSummary.completedCount} completed`}
          </span>
        ) : null}

        {showClearUploads ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearCompletedUploads}
          >
            Clear completed
          </Button>
        ) : null}
      </div>

      {disabledReason && !runOnUploadEnabled ? (
        <p className="mt-2 text-xs text-slate-500">{disabledReason}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <DocumentsViewTabs view={view} onChange={onChangeView} />
        <StatusFilterControl
          selectedStatuses={selectedStatuses}
          onToggleStatus={onToggleStatus}
          onClearStatuses={onClearStatuses}
        />
        <Select
          value={sort}
          onChange={(e) => onSort(e.target.value as SortOption)}
          className="w-40"
          aria-label="Sort documents"
        >
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="-last_run_at">Recent runs</option>
          <option value="last_run_at">Least recently run</option>
          <option value="-byte_size">Largest files</option>
          <option value="byte_size">Smallest files</option>
          <option value="name">Name A–Z</option>
          <option value="-name">Name Z–A</option>
        </Select>
        <span
          className={clsx(
            "ml-auto inline-flex items-center gap-1 text-[11px] text-slate-500",
            isFetching ? "opacity-100" : "opacity-0",
          )}
          role="status"
          aria-live="polite"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
          Updating…
        </span>
      </div>
    </section>
  );
}

function BatchRunDialog({
  open,
  workspaceId,
  documentIds,
  documentsById,
  configurations,
  preferredConfigId,
  configurationsLoading,
  configurationsError,
  configurationsErrorMessage,
  onClose,
  onViewRun,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: {
  open: boolean;
  workspaceId: string;
  documentIds: readonly string[];
  documentsById: Map<string, DocumentRecord>;
  configurations: ConfigurationRecord[];
  preferredConfigId: string;
  configurationsLoading: boolean;
  configurationsError: boolean;
  configurationsErrorMessage?: string;
  onClose: () => void;
  onViewRun: (document: DocumentRecord, runId?: string | null) => void;
  safeModeEnabled?: boolean;
  safeModeMessage?: string;
  safeModeLoading?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();
  const submitBatch = useSubmitRunsBatch(workspaceId);
  const [selectedConfigId, setSelectedConfigId] = useState("");
  const [createdRuns, setCreatedRuns] = useState<RunResource[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setErrorMessage(null);
      setCreatedRuns(null);
      return;
    }
    setSelectedConfigId((current) => {
      if (current && configurations.some((config) => config.id === current)) {
        return current;
      }
      return preferredConfigId;
    });
  }, [configurations, open, preferredConfigId]);

  useEffect(() => {
    if (!open) return;
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
  }, [onClose, open]);

  if (typeof window === "undefined" || !open) return null;

  const hasConfigurations = configurations.length > 0;
  const safeModeDetail = safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE;
  const runDisabled =
    safeModeEnabled ||
    safeModeLoading ||
    submitBatch.isPending ||
    documentIds.length === 0 ||
    !selectedConfigId;

  const handleSubmit = () => {
    if (safeModeEnabled || safeModeLoading) {
      return;
    }
    if (!selectedConfigId) {
      setErrorMessage("Select a configuration to run.");
      return;
    }
    setErrorMessage(null);
    submitBatch.mutate(
      { configId: selectedConfigId, documentIds },
      {
        onSuccess: (runs) => {
          setCreatedRuns(runs);
        },
        onError: (error) => {
          const message = resolveApiErrorMessage(error, "Unable to submit batch runs.");
          setErrorMessage(message);
        },
      },
    );
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/50"
        onClick={onClose}
        aria-label="Close dialog"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="relative w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"
      >
        <header className="space-y-1">
          <h2 id={titleId} className="text-lg font-semibold text-slate-900">
            Run extraction on selected documents
          </h2>
          <p id={descriptionId} className="text-xs text-slate-500">
            {documentIds.length.toLocaleString()} document{documentIds.length === 1 ? "" : "s"} selected.
          </p>
        </header>

        <div className="mt-4 space-y-4 text-sm text-slate-600">
          {safeModeEnabled ? <Alert tone="warning">{safeModeDetail}</Alert> : null}
          {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}

          {createdRuns ? (
            <section className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Batch queued</p>
              <div className="space-y-2">
                {createdRuns.length === 0 ? (
                  <p className="text-xs text-slate-500">No runs were created.</p>
                ) : (
                  createdRuns.map((run) => {
                    const documentId = run.input?.document_id ?? null;
                    const document = documentId ? documentsById.get(documentId) ?? null : null;
                    const title = document?.name ?? (documentId ? `Document ${documentId}` : "Document");
                    return (
                      <div key={run.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-800" title={title}>
                              {title}
                            </p>
                            <p className="text-xs text-slate-500">{run.id}</p>
                          </div>
                          {document ? (
                            <Button size="sm" variant="ghost" onClick={() => onViewRun(document, run.id)}>
                              View run
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </section>
          ) : (
            <>
              <section className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Configuration</p>
                {configurationsLoading ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                    Loading configurations…
                  </div>
                ) : configurationsError ? (
                  <Alert tone="danger">
                    {configurationsErrorMessage ?? "Unable to load configurations."}
                  </Alert>
                ) : hasConfigurations ? (
                  <Select
                    value={selectedConfigId}
                    onChange={(event) => setSelectedConfigId(event.target.value)}
                    disabled={safeModeEnabled}
                  >
                    <option value="">Select configuration</option>
                    {configurations.map((config) => (
                      <option key={config.id} value={config.id}>
                        {formatConfigurationLabel(config)}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Alert tone="info">No configurations available. Create one before running extraction.</Alert>
                )}
              </section>
              <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Batch runs process the entire document. Sheet selection is not available for this action.
              </p>
            </>
          )}
        </div>

        <footer className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={submitBatch.isPending}>
            {createdRuns ? "Close" : "Cancel"}
          </Button>
          {!createdRuns ? (
            <Button
              onClick={handleSubmit}
              isLoading={submitBatch.isPending}
              disabled={runDisabled}
              title={
                safeModeEnabled
                  ? safeModeDetail
                  : !selectedConfigId
                    ? "Select a configuration to run extraction."
                    : undefined
              }
            >
              Run extraction
            </Button>
          ) : null}
        </footer>
      </div>
    </div>,
    window.document.body,
  );
}

function DocumentsViewTabs({ view, onChange }: { view: DocumentsView; onChange: (view: DocumentsView) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(DOCUMENT_VIEW_PRESETS) as DocumentsView[]).map((key) => {
        const preset = DOCUMENT_VIEW_PRESETS[key];
        const active = key === view;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-medium transition",
              active
                ? "bg-brand-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900",
            )}
            title={preset.description}
          >
            {preset.label}
          </button>
        );
      })}
    </div>
  );
}

function StatusFilterControl({
  selectedStatuses,
  onToggleStatus,
  onClearStatuses,
}: {
  selectedStatuses: ReadonlySet<DocumentStatus>;
  onToggleStatus: (status: DocumentStatus) => void;
  onClearStatuses: () => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const statusEntries = Object.entries(DOCUMENT_STATUS_LABELS) as [DocumentStatus, string][];
  const hasSelection = selectedStatuses.size > 0;
  const summaryLabel = hasSelection
    ? `${selectedStatuses.size} ${selectedStatuses.size === 1 ? "status" : "statuses"}`
    : "All statuses";

  useEffect(() => {
    if (!open) return undefined;
    const onClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 shadow-sm hover:border-slate-300"
        aria-haspopup="true"
        aria-expanded={open}
      >
        Status: {summaryLabel}
        <ChevronDownIcon className="h-3 w-3" />
      </button>
      {open ? (
        <div className="absolute z-30 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-3 text-sm shadow-xl">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Status filters</span>
            <button
              type="button"
              onClick={() => {
                onClearStatuses();
                setOpen(false);
              }}
              className={clsx(
                "text-[11px]",
                hasSelection ? "text-slate-500 underline underline-offset-4" : "text-slate-300",
              )}
            >
              Clear
            </button>
          </div>
          <ul className="space-y-1 text-xs text-slate-600">
            {statusEntries.map(([status, label]) => {
              const active = selectedStatuses.has(status);
              return (
                <li key={status}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={active}
                      onChange={() => onToggleStatus(status)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                      <span className="truncate">{label}</span>
                  </label>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 flex justify-end">
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Done
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
/* ----------------------------- Documents table ----------------------------- */

interface DocumentsTableProps {
  readonly rows: readonly DocumentTableRow[];
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
  readonly renderRunStatus?: (document: DocumentRecord) => ReactNode;
  readonly onViewRun?: (document: DocumentRecord, runId?: string | null) => void;
  readonly onCancelUpload?: (itemId: string) => void;
  readonly onRetryUpload?: (itemId: string) => void;
  readonly onRemoveUpload?: (itemId: string) => void;
  readonly currentUserLabel?: string;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function DocumentsTable({
  rows,
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
  renderRunStatus,
  onViewRun,
  onCancelUpload,
  onRetryUpload,
  onRemoveUpload,
  currentUserLabel,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DocumentsTableProps) {
  const headerCheckboxRef = useRef<HTMLInputElement | null>(null);
  const resolvedUserLabel = currentUserLabel ?? "You";

  const selectableIds = useMemo(() => {
    return rows.flatMap((row) => (row.document ? [row.document.id] : []));
  }, [rows]);

  const { allSelected, someSelected } = useMemo(() => {
    if (selectableIds.length === 0) return { allSelected: false, someSelected: false };
    const selectedCount = selectableIds.reduce(
      (count, id) => (selectedIds.has(id) ? count + 1 : count),
      0,
    );
    return {
      allSelected: selectedCount === selectableIds.length,
      someSelected: selectedCount > 0 && selectedCount < selectableIds.length,
    };
  }, [selectableIds, selectedIds]);

  useEffect(() => {
    if (headerCheckboxRef.current) headerCheckboxRef.current.indeterminate = someSelected;
  }, [someSelected]);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full table-fixed border-separate border-spacing-0 text-sm text-slate-700">
        <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          <tr className="border-b border-slate-200">
            <th scope="col" className="w-10 px-2 py-2">
              <input
                ref={headerCheckboxRef}
                type="checkbox"
                className="h-4 w-4 rounded border border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                checked={allSelected}
                onChange={onToggleAll}
                disabled={disableSelection || selectableIds.length === 0}
              />
            </th>
            <th scope="col" className="w-20 px-2 py-2 text-left">ID</th>
            <th scope="col" className="px-2 py-2 text-left">Document</th>
            <th scope="col" className="w-40 px-2 py-2 text-left">Uploaded</th>
            <th scope="col" className="w-48 px-2 py-2 text-left">Uploader</th>
            <th scope="col" className="w-48 px-2 py-2 text-left">Latest run</th>
            <th scope="col" className="w-44 px-2 py-2 text-left">Status</th>
            <th scope="col" className="w-36 px-2 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const document = row.document;
            const upload = row.upload;
            const isSelected = document ? selectedIds.has(document.id) : false;
            const hasActiveUpload = Boolean(upload) && upload.status !== "succeeded";
            const rowTone = isSelected ? "bg-brand-50/50" : hasActiveUpload ? "bg-slate-50/60" : "bg-white";
            const uploaderLabel = document
              ? document.uploader?.name ?? document.uploader?.email ?? "—"
              : resolvedUserLabel;
            const showDocumentActions = Boolean(document) && (!upload || upload.status === "succeeded");
            const documentTags = document?.tags ?? [];
            return (
              <tr
                key={row.key}
                className={clsx(
                  "border-b border-slate-200 last:border-b-0 transition-colors hover:bg-slate-50",
                  rowTone,
                )}
              >
                <td className="px-2 py-2 align-middle">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    checked={isSelected}
                    onChange={() => {
                      if (document) {
                        onToggleDocument(document.id);
                      }
                    }}
                    disabled={disableSelection || !document}
                  />
                </td>
                <td className="px-2 py-2 align-middle font-mono text-xs text-slate-500">
                  {document ? document.id.slice(-6) : "—"}
                </td>
                <td className="px-2 py-2 align-middle">
                  <div className="min-w-0">
                    <div
                      className="truncate font-semibold text-slate-900"
                      title={document?.name ?? upload?.file.name}
                    >
                      {document?.name ?? upload?.file.name ?? "Untitled file"}
                    </div>
                    <div className="text-xs text-slate-500">
                      {document
                        ? formatFileDescription(document)
                        : upload
                          ? formatUploadFileDescription(upload)
                          : "Pending upload"}
                    </div>
                    {documentTags.length ? (
                      <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-500">
                        {documentTags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600"
                          >
                            #{tag}
                          </span>
                        ))}
                        {documentTags.length > 3 ? (
                          <span className="px-1 text-[10px] text-slate-400">
                            +{documentTags.length - 3}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </td>
                <td className="px-2 py-2 align-middle">
                  {document ? (
                    <time
                      dateTime={document.created_at}
                      className="block text-xs text-slate-600"
                      title={uploadedFormatter.format(new Date(document.created_at))}
                    >
                      {formatUploadedAt(document)}
                    </time>
                  ) : upload ? (
                    <span className="block text-xs text-slate-500">
                      {formatUploadTimestamp(upload)}
                    </span>
                  ) : null}
                </td>
                <td className="px-2 py-2 align-middle">
                  <span className="block truncate text-xs text-slate-600">
                    {uploaderLabel}
                  </span>
                </td>
                <td className="px-2 py-2 align-middle">
                  {row.runState ? (
                    <UploadRunStatus
                      runState={row.runState}
                      document={document ?? undefined}
                      onViewRun={onViewRun}
                    />
                  ) : document ? (
                    renderRunStatus ? renderRunStatus(document) : null
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>
                <td className="px-2 py-2 align-middle">
                  {upload && upload.status !== "succeeded" ? (
                    <UploadStatusCell upload={upload} />
                  ) : document ? (
                    <span
                      className={clsx(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                        statusBadgeClass(document.status),
                      )}
                    >
                      {formatStatusLabel ? formatStatusLabel(document.status) : document.status}
                    </span>
                  ) : upload ? (
                    <UploadStatusCell upload={upload} />
                  ) : null}
                </td>
                <td className="px-2 py-2 align-middle text-right">
                  {showDocumentActions && document ? (
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
                  ) : upload ? (
                    <UploadActions
                      upload={upload}
                      onCancel={onCancelUpload}
                      onRetry={onRetryUpload}
                      onRemove={onRemoveUpload}
                      disabled={disableRowActions}
                    />
                  ) : null}
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

function UploadActions({
  upload,
  onCancel,
  onRetry,
  onRemove,
  disabled = false,
}: {
  upload: UploadItem;
  onCancel?: (itemId: string) => void;
  onRetry?: (itemId: string) => void;
  onRemove?: (itemId: string) => void;
  disabled?: boolean;
}) {
  const canCancel = Boolean(onCancel) && (upload.status === "uploading" || upload.status === "queued");
  const canRetry = Boolean(onRetry) && upload.status === "failed";
  const canRemove = Boolean(onRemove) && (upload.status === "failed" || upload.status === "cancelled");

  return (
    <div className="inline-flex items-center gap-1.5 justify-end">
      {canCancel ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onCancel?.(upload.id)}
          disabled={disabled}
        >
          Cancel
        </Button>
      ) : null}
      {canRetry ? (
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onRetry?.(upload.id)}
          disabled={disabled}
        >
          Retry
        </Button>
      ) : null}
      {canRemove ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onRemove?.(upload.id)}
          disabled={disabled}
        >
          Remove
        </Button>
      ) : null}
    </div>
  );
}

function UploadRunStatus({
  runState,
  document,
  onViewRun,
}: {
  runState: UploadRunState;
  document?: DocumentRecord;
  onViewRun?: (document: DocumentRecord, runId?: string | null) => void;
}) {
  if (runState.status === "pending") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-slate-500">
        <SpinnerIcon className="h-3.5 w-3.5" />
        Queueing run…
      </span>
    );
  }

  if (runState.status === "queued") {
    return (
      <div className="flex flex-col gap-1 text-xs">
        <span className="text-emerald-700">Run queued</span>
        {runState.runId ? (
          <span className="text-[11px] text-slate-400">{runState.runId}</span>
        ) : null}
        {document && runState.runId && onViewRun ? (
          <button
            type="button"
            className="text-emerald-700 underline underline-offset-4"
            onClick={() => onViewRun(document, runState.runId)}
          >
            View run
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <span className="text-xs text-rose-600">
      Failed{runState.error ? `: ${runState.error}` : ""}
    </span>
  );
}

function UploadStatusCell({ upload }: { upload: UploadItem }) {
  const statusLabel = formatUploadStatus(upload.status);
  const statusTone = uploadStatusBadgeClass(upload.status);
  const canShowProgress = upload.status === "uploading" || upload.status === "queued";
  const progressText = `${formatFileSize(upload.progress.loaded)} of ${formatFileSize(upload.progress.total)}`;

  return (
    <div className="space-y-1">
      <span
        className={clsx(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
          statusTone,
        )}
      >
        {statusLabel}
      </span>
      {canShowProgress ? (
        <div className="space-y-1 text-[11px] text-slate-500">
          <div className="flex items-center justify-between">
            <span>{progressText}</span>
            <span>{upload.progress.percent}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-slate-100">
            <div
              className="h-1.5 rounded-full bg-brand-500 transition"
              style={{ width: `${upload.progress.percent}%` }}
            />
          </div>
        </div>
      ) : null}
      {upload.error ? <span className="text-[11px] text-rose-600">{upload.error}</span> : null}
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

function formatUploadFileDescription(upload: UploadItem) {
  const parts: string[] = [];
  if (upload.file.type) parts.push(humanizeContentType(upload.file.type));
  if (upload.file.size >= 0) parts.push(formatFileSize(upload.file.size));
  return parts.join(" • ") || "Pending upload";
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

function formatUploadTimestamp(upload: UploadItem) {
  switch (upload.status) {
    case "queued":
      return "Queued";
    case "uploading":
      return "Uploading…";
    case "succeeded":
      return "Uploaded";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return upload.status;
  }
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

function resolveSelectableConfigs(configurations: ConfigurationRecord[]) {
  const selectableConfigs = configurations
    .filter((config) => !("deleted_at" in config && (config as { deleted_at?: string | null }).deleted_at))
    .filter((config) => {
      const statusLabel = typeof config.status === "string" ? config.status.toLowerCase() : "draft";
      return statusLabel !== "archived";
    })
    .sort((a, b) => {
      const statusA = typeof a.status === "string" ? a.status.toLowerCase() : "draft";
      const statusB = typeof b.status === "string" ? b.status.toLowerCase() : "draft";
      if (statusA === "active" && statusB !== "active") return -1;
      if (statusB === "active" && statusA !== "active") return 1;
      const updatedA = new Date((a as { updated_at?: string | null }).updated_at ?? 0).getTime();
      const updatedB = new Date((b as { updated_at?: string | null }).updated_at ?? 0).getTime();
      return updatedB - updatedA;
    });
  const activeConfig =
    selectableConfigs.find((config) => (typeof config.status === "string" ? config.status.toLowerCase() : "") === "active") ??
    null;
  return { selectableConfigs, activeConfig };
}

function formatConfigurationLabel(config: ConfigurationRecord) {
  const statusLabel = typeof config.status === "string" ? config.status : "draft";
  const title = (config as { title?: string | null }).title ?? config.display_name ?? "Untitled configuration";
  return `${title} (${statusLabel.charAt(0).toUpperCase()}${statusLabel.slice(1)})`;
}

function formatUploadStatus(status: UploadItem["status"]) {
  switch (status) {
    case "queued":
      return "Queued";
    case "uploading":
      return "Uploading";
    case "succeeded":
      return "Uploaded";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

function uploadStatusBadgeClass(status: UploadItem["status"]) {
  switch (status) {
    case "succeeded":
      return "bg-success-100 text-success-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "uploading":
      return "bg-brand-100 text-brand-700";
    case "cancelled":
      return "bg-slate-200 text-slate-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function isTerminalUploadStatus(status: UploadItem["status"]) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
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

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <path d="M5 8l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={clsx("animate-spin text-slate-500", className)}
      role="presentation"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-75"
        d="M22 12c0-5.523-4.477-10-10-10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}
/* --------------------------------- Run Drawer --------------------------------- */

interface RunExtractionDrawerProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord | null;
  readonly initialRunId?: string | null;
  readonly onClose: () => void;
  readonly onRunSuccess?: (run: RunResource) => void;
  readonly onRunError?: (message: string) => void;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function RunExtractionDrawer({
  open,
  workspaceId,
  documentRecord,
  initialRunId,
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
      initialRunId={initialRunId}
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
  readonly initialRunId?: string | null;
  readonly onClose: () => void;
  readonly onRunSuccess?: (run: RunResource) => void;
  readonly onRunError?: (message: string) => void;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function RunExtractionDrawerContent({
  workspaceId,
  documentRecord,
  initialRunId,
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
  const navigate = useNavigate();
  const configurationsQuery = useConfigurationsQuery({ workspaceId });
  const [selectedConfigId, setSelectedConfigId] = useState<string>("");
  const submitRun = useSubmitRun(workspaceId);
  const { preferences, setPreferences } = useDocumentRunPreferences(
    workspaceId,
    documentRecord.id,
  );
  const [activeRunId, setActiveRunId] = useState<string | null>(
    initialRunId ?? documentRecord.last_run?.run_id ?? null,
  );

  useEffect(() => {
    const next = initialRunId ?? documentRecord.last_run?.run_id ?? null;
    setActiveRunId(next);
  }, [documentRecord.id, documentRecord.last_run?.run_id, initialRunId]);

  const allConfigs = useMemo(() => configurationsQuery.data?.items ?? [], [configurationsQuery.data]);
  const { selectableConfigs, activeConfig } = useMemo(
    () => resolveSelectableConfigs(allConfigs),
    [allConfigs],
  );
  const hasActiveConfig = Boolean(activeConfig);

  const preferredConfigId = useMemo(() => {
    if (activeConfig?.id) {
      return activeConfig.id;
    }
    if (preferences.configId) {
      const match = selectableConfigs.find((config) => config.id === preferences.configId);
      if (match) {
        return match.id;
      }
    }
    return selectableConfigs[0]?.id ?? "";
  }, [activeConfig?.id, preferences.configId, selectableConfigs]);

  useEffect(() => {
    setSelectedConfigId((current) => {
      if (current && selectableConfigs.some((config) => config.id === current)) {
        return current;
      }
      return preferredConfigId;
    });
  }, [preferredConfigId, selectableConfigs]);

  const selectedConfig = useMemo(
    () => selectableConfigs.find((config) => config.id === selectedConfigId) ?? null,
    [selectableConfigs, selectedConfigId],
  );

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const safeModeDetail = safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE;

  const runQuery = useQuery({
    queryKey: activeRunId ? runQueryKeys.detail(activeRunId) : ["run", "none"],
    queryFn: ({ signal }) =>
      activeRunId ? fetchRun(activeRunId, signal) : Promise.reject(new Error("No run selected")),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "queued" ? 2000 : false;
    },
  });

  const telemetryQuery = useQuery({
    queryKey: activeRunId ? runQueryKeys.telemetry(activeRunId) : ["run-telemetry", "none"],
    queryFn: ({ signal }) => {
      if (!activeRunId) {
        return Promise.reject(new Error("No run selected"));
      }
      const run = runQuery.data ?? activeRunId;
      return fetchRunTelemetry(run, signal);
    },
    enabled:
      Boolean(activeRunId) &&
      (runQuery.data?.status === "succeeded" || runQuery.data?.status === "failed"),
    staleTime: 5_000,
  });

  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["document-sheets", workspaceId, documentRecord.id],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, documentRecord.id, signal),
    staleTime: 60_000,
  });
  const sheetParseFailed =
    sheetQuery.error instanceof ApiError && sheetQuery.error.status === 422;
  const sheetOptions = useMemo(
    () => sheetQuery.data ?? [],
    [sheetQuery.data],
  );
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);

  useEffect(() => {
    if (!sheetOptions.length) {
      setSelectedSheets([]);
      return;
    }
    const preferred = (preferences.sheetNames ?? []).filter((sheetName) =>
      sheetOptions.some((sheet) => sheet.name === sheetName),
    );
    const uniquePreferred = Array.from(new Set(preferred));
    setSelectedSheets(uniquePreferred);
  }, [sheetOptions, preferences.sheetNames]);

  const normalizedSheetSelection = useMemo(
    () =>
      Array.from(
        new Set(selectedSheets.filter((name) => sheetOptions.some((sheet) => sheet.name === name))),
      ),
    [selectedSheets, sheetOptions],
  );

  useEffect(() => {
    if (!selectedConfig) {
      return;
    }
    setPreferences({
      configId: selectedConfig.id,
      sheetNames: normalizedSheetSelection.length ? normalizedSheetSelection : null,
    });
  }, [normalizedSheetSelection, selectedConfig, setPreferences]);

  const toggleWorksheet = useCallback((name: string) => {
    setSelectedSheets((current) =>
      current.includes(name) ? current.filter((sheet) => sheet !== name) : [...current, name],
    );
  }, []);

  const currentRun = runQuery.data ?? null;
  const runStatus = currentRun?.status ?? null;
  const runRunning = runStatus === "running" || runStatus === "queued";
  const outputUrl = currentRun ? runOutputUrl(currentRun) : null;
  const outputPath = currentRun?.output?.output_path ?? null;
  const logsUrl = currentRun ? runLogsUrl(currentRun) : null;
  const telemetryEvents = telemetryQuery.data ?? [];
  const summary = useMemo(
    () => extractRunSummaryFromTelemetry(telemetryQuery.data ?? []),
    [telemetryQuery.data],
  );

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
    submitRun.isPending ||
    runRunning ||
    safeModeLoading ||
    safeModeEnabled ||
    !hasConfigurations ||
    !selectedConfig;
  const runButtonTitle = safeModeEnabled
    ? safeModeDetail
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : !hasConfigurations
        ? "No configurations available. Create one before running extraction."
        : !selectedConfig
          ? "Select a configuration to run extraction."
      : undefined;

  const handleSubmit = () => {
    if (safeModeEnabled || safeModeLoading) {
      return;
    }
    if (!selectedConfig) {
      setErrorMessage("Select a configuration before running the extractor.");
      return;
    }
    setErrorMessage(null);
    setActiveRunId(null);
    const sheetList = normalizedSheetSelection;
    const baseRunOptions = {
      dry_run: false,
      validate_only: false,
      force_rebuild: false,
      debug: false,
      log_level: "INFO",
    } as const;
    const runOptions =
      sheetList.length > 0
        ? { ...baseRunOptions, input_sheet_names: sheetList }
        : baseRunOptions;
    submitRun.mutate(
      {
        configId: selectedConfig.id,
        documentId: documentRecord.id,
        options: runOptions,
      },
      {
        onSuccess: (run) => {
          setPreferences({
            configId: selectedConfig.id,
            sheetNames: sheetList.length ? sheetList : null,
          });
          onRunSuccess?.(run);
          setActiveRunId(run.id);
        },
        onError: (error) => {
          const message = error instanceof Error ? error.message : "Unable to submit extraction run.";
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
            <p id={descriptionId} className="text-xs text-slate-500">Prepare and submit a processing run.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitRun.isPending}>
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
            <DocumentTagsEditor
              workspaceId={workspaceId}
              documentRecord={documentRecord}
            />
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Configuration</p>
            {configurationsQuery.isLoading ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Loading configurations…
              </div>
            ) : configurationsQuery.isError ? (
              <Alert tone="danger">
                Unable to load configurations.{" "}
                {configurationsQuery.error instanceof Error ? configurationsQuery.error.message : "Try again later."}
              </Alert>
            ) : hasConfigurations ? (
              <div className="space-y-2">
                {!hasActiveConfig ? (
                  <div className="space-y-2">
                    <Alert tone="warning">
                      No active configuration. Runs will use the selected draft configuration.
                    </Alert>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        onClose();
                        navigate(`/workspaces/${workspaceId}/config-builder`);
                      }}
                      disabled={submitRun.isPending}
                    >
                      Go to Configuration Builder
                    </Button>
                  </div>
                ) : null}
                <Select
                  value={selectedConfigId}
                  onChange={(event) => {
                    const value = event.target.value;
                    setSelectedConfigId(value);
                  }}
                  disabled={submitRun.isPending}
                >
                  <option value="">Select configuration</option>
                  {selectableConfigs.map((config) => (
                    <option key={config.id} value={config.id}>
                      {formatConfigurationLabel(config)}
                    </option>
                  ))}
                </Select>
              </div>
            ) : (
              <Alert tone="info">No configurations available. Create one before running extraction.</Alert>
            )}
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Advanced options</p>
            {sheetQuery.isLoading ? (
              <p className="text-xs text-slate-500">Loading worksheets…</p>
            ) : sheetParseFailed ? (
              <Alert tone="warning">
                <p className="text-xs text-slate-700">
                  Worksheet inspection failed for this file. ADE will process the full document and
                  sheet selection is disabled.
                </p>
              </Alert>
            ) : sheetQuery.isError ? (
              <Alert tone="warning">
                <div className="space-y-2">
                  <p className="text-xs text-slate-700">
                    Worksheet metadata is temporarily unavailable. The run will process the entire
                    file unless you retry and pick specific sheets.
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => sheetQuery.refetch()}
                      disabled={sheetQuery.isFetching}
                    >
                      Retry loading
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedSheets([])}
                      disabled={submitRun.isPending}
                    >
                      Use all worksheets
                    </Button>
                  </div>
                </div>
              </Alert>
            ) : sheetOptions.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-slate-600">Worksheets</p>
                    <p className="text-[11px] text-slate-500">
                      {normalizedSheetSelection.length === 0
                        ? "All worksheets will be processed by default. Select any subset to narrow the run."
                        : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                            normalizedSheetSelection.length === 1 ? "" : "s"
                          } selected. Clear selections to process every sheet.`}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedSheets([])}
                disabled={submitRun.isPending}
              >
                Use all worksheets
                  </Button>
                </div>

                <div className="max-h-48 space-y-2 overflow-auto rounded-md border border-slate-200 p-2">
                  {sheetOptions.map((sheet) => {
                    const checked = normalizedSheetSelection.includes(sheet.name);
                    return (
                      <label
                        key={`${sheet.index}-${sheet.name}`}
                        className="flex items-center gap-2 rounded px-2 py-1 text-sm text-slate-700 hover:bg-slate-100"
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                          checked={checked}
                          onChange={() => toggleWorksheet(sheet.name)}
                        />
                        <span className="flex-1 truncate">
                          {sheet.name}
                          {sheet.is_active ? " (active)" : ""}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                This document does not expose multiple worksheets, so ADE will ingest the uploaded file directly.
              </p>
            )}
          </section>

          {activeRunId ? (
            <section className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Latest run</p>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-800" title={activeRunId}>
                      Run {activeRunId}
                    </p>
                    <p className="text-xs text-slate-500">
                      Status: {runStatus ?? "loading…"}
                    </p>
                  </div>
                  {runRunning ? <SpinnerIcon className="h-4 w-4 text-slate-500" /> : null}
                </div>

                {logsUrl ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <a
                      href={logsUrl}
                      className="inline-flex items-center rounded border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
                    >
                      Download logs
                    </a>
                  </div>
                ) : null}

                <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-slate-700">Output</p>
                  {runQuery.isFetching && !outputUrl ? (
                    <p className="text-xs text-slate-500">Loading output…</p>
                  ) : outputUrl ? (
                    <div className="mt-1 flex items-center justify-between gap-2 break-all rounded border border-slate-100 px-2 py-1 text-xs text-slate-700">
                      <a href={outputUrl} className="text-emerald-700 hover:underline">
                        {outputPath?.split("/").pop() ?? "Download output"}
                      </a>
                      {outputPath ? <span className="text-[11px] text-slate-500">{outputPath}</span> : null}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">Output will appear here after the run completes.</p>
                  )}
	                </div>
	                <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
	                  <p className="text-xs font-semibold text-slate-700">Run summary</p>
	                  {telemetryQuery.isLoading ? (
	                    <p className="text-xs text-slate-500">Loading summary…</p>
	                  ) : telemetryQuery.isError ? (
	                    <p className="text-xs text-rose-600">Unable to load run summary.</p>
	                  ) : summary ? (
	                    <RunSummaryView summary={summary} />
	                  ) : (
	                    <p className="text-xs text-slate-500">Summary not available.</p>
	                  )}
	                </div>
                <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-slate-700">Telemetry summary</p>
                  {telemetryQuery.isLoading ? (
                    <p className="text-xs text-slate-500">Loading telemetry…</p>
                  ) : telemetryQuery.isError ? (
                    <p className="text-xs text-rose-600">Unable to load telemetry events.</p>
                  ) : telemetryEvents.length > 0 ? (
                    <TelemetrySummary events={telemetryEvents} />
                  ) : (
                    <p className="text-xs text-slate-500">No telemetry events captured.</p>
                  )}
                </div>
              </div>
            </section>
          ) : null}

          {safeModeEnabled ? <Alert tone="warning">{safeModeDetail}</Alert> : null}
          {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitRun.isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            isLoading={submitRun.isPending}
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

function DocumentTagsEditor({
  workspaceId,
  documentRecord,
}: {
  workspaceId: string;
  documentRecord: DocumentRecord;
}) {
  const queryClient = useQueryClient();
  const [draftTags, setDraftTags] = useState<string[]>(() => documentRecord.tags ?? []);
  const [savedTags, setSavedTags] = useState<string[]>(() => documentRecord.tags ?? []);
  const [inputValue, setInputValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const next = documentRecord.tags ?? [];
    setDraftTags(next);
    setSavedTags(next);
    setInputValue("");
    setError(null);
  }, [documentRecord.id, (documentRecord.tags ?? []).join("|")]);

  const saveTags = useMutation({
    mutationFn: (nextTags: string[]) =>
      replaceDocumentTags(workspaceId, documentRecord.id, nextTags),
    onSuccess: (updated) => {
      const next = updated.tags ?? [];
      setDraftTags(next);
      setSavedTags(next);
      setError(null);
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
    onError: (err) => {
      setError(resolveApiErrorMessage(err, "Unable to update tags."));
    },
  });

  const suggestionsQuery = useQuery({
    queryKey: ["tag-catalog", workspaceId],
    queryFn: ({ signal }) =>
      fetchTagCatalog(
        workspaceId,
        {
          page: 1,
          page_size: 8,
          sort: "-count",
        },
        signal,
      ),
    enabled: workspaceId.length > 0,
    staleTime: 30_000,
  });

  const suggestedTags = useMemo(() => {
    const items = suggestionsQuery.data?.items ?? [];
    return items.map((item) => item.tag).filter((tag) => !draftTags.includes(tag));
  }, [draftTags, suggestionsQuery.data?.items]);

  const isDirty = !areTagsEqual(savedTags, draftTags);
  const tagLimitReached = draftTags.length >= MAX_DOCUMENT_TAGS;

  const addTags = useCallback((raw: string) => {
    const tokens = splitTagInput(raw);
    if (tokens.length === 0) return;
    setDraftTags((current) => {
      const next = new Set(current);
      for (const token of tokens) {
        if (next.size >= MAX_DOCUMENT_TAGS) break;
        next.add(token);
      }
      return Array.from(next).sort();
    });
    setInputValue("");
  }, []);

  const removeTag = useCallback((tag: string) => {
    setDraftTags((current) => current.filter((entry) => entry !== tag));
  }, []);

  const handleSave = () => {
    if (!isDirty) return;
    saveTags.mutate(draftTags);
  };

  const handleReset = () => {
    setDraftTags(savedTags);
    setInputValue("");
    setError(null);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Tags</p>
        {isDirty ? (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-600">Unsaved</span>
        ) : (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600">Saved</span>
        )}
      </div>

      <div className="flex flex-wrap gap-1">
        {draftTags.length > 0 ? (
          draftTags.map((tag) => (
            <span
              key={tag}
              className="group inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700"
            >
              #{tag}
              <button
                type="button"
                className="rounded-full px-1 text-[10px] text-slate-400 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                onClick={() => removeTag(tag)}
                aria-label={`Remove tag ${tag}`}
              >
                x
              </button>
            </span>
          ))
        ) : (
          <span className="text-xs text-slate-400">No tags yet.</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Input
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              addTags(inputValue);
            }
          }}
          placeholder="Add tags (comma separated)"
          disabled={tagLimitReached || saveTags.isPending}
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => addTags(inputValue)}
          disabled={!inputValue.trim() || tagLimitReached || saveTags.isPending}
        >
          Add
        </Button>
      </div>

      {tagLimitReached ? (
        <p className="text-[11px] text-amber-600">
          Tag limit reached ({MAX_DOCUMENT_TAGS} max).
        </p>
      ) : null}

      {suggestedTags.length ? (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Suggested</p>
          <div className="flex flex-wrap gap-1">
            {suggestedTags.map((tag) => (
              <button
                key={tag}
                type="button"
                className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500 hover:border-slate-300 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                onClick={() => addTags(tag)}
              >
                +{tag}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {error ? <p className="text-xs text-rose-600">{error}</p> : null}

      <div className="flex justify-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={handleReset}
          disabled={!isDirty || saveTags.isPending}
        >
          Reset
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={handleSave}
          isLoading={saveTags.isPending}
          disabled={!isDirty || saveTags.isPending}
        >
          Save tags
        </Button>
      </div>
    </div>
  );
}

function splitTagInput(value: string): string[] {
  return value
    .split(",")
    .map((token) => normalizeTagInput(token))
    .filter(Boolean);
}

function normalizeTagInput(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function areTagsEqual(left: readonly string[], right: readonly string[]): boolean {
  if (left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return false;
  }
  return true;
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
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => !runDisabled && onRun()} disabled={runDisabled} title={runTitle}>
            Run extraction
          </Button>
          <Button size="sm" variant="danger" onClick={onDelete} disabled={busy} isLoading={busy}>
            Delete selected
          </Button>
        </div>
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

function extractRunSummaryFromTelemetry(events: RunStreamEvent[]): Partial<RunSummary> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    const name = typeof event.event === "string" ? event.event : typeof event.type === "string" ? event.type : null;
    if (name !== "engine.run.summary") {
      continue;
    }
    const payload = event.data;
    if (payload && typeof payload === "object") {
      return payload as Partial<RunSummary>;
    }
  }
  return null;
}

/* ------------------------------ Run status chip ------------------------------ */

function DocumentRunStatus({ document }: { document: DocumentRecord }) {
  const lastRun = document.last_run;
  if (!lastRun) return <span className="text-xs text-slate-400">No runs yet</span>;

  return (
    <div className="flex flex-col gap-1">
      <span
        className={clsx(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
          runStatusBadgeClass(lastRun.status as RunStatus),
        )}
      >
        {formatRunStatus(lastRun.status as RunStatus)}
        {lastRun.run_at ? (
          <span className="ml-1 font-normal text-slate-500">{formatRelativeTime(lastRun.run_at)}</span>
        ) : null}
      </span>
      {lastRun.message ? <span className="text-[11px] text-slate-500">{lastRun.message}</span> : null}
    </div>
  );
}

function runStatusBadgeClass(status: RunStatus) {
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

function formatRunStatus(status: RunStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
function formatRelativeTime(value?: string | null) {
  if (!value) return "unknown";
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
