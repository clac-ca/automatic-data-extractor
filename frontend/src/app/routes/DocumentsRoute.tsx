import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ChangeEvent, ReactNode, RefObject } from "react";
import { useSearchParams } from "react-router-dom";
import clsx from "clsx";

import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import { useUploadDocumentsMutation } from "../../features/documents/hooks/useUploadDocumentsMutation";
import { useDeleteDocumentsMutation } from "../../features/documents/hooks/useDeleteDocumentsMutation";
import type { WorkspaceDocumentSummary } from "../../shared/types/documents";
import { PageState } from "../components/PageState";
import { Alert, Button, Input } from "../../ui";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { trackEvent } from "../../shared/telemetry/events";
import { ApiError } from "../../shared/api/client";

const PAGE_SIZE = 50;

const STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "inbox", label: "Inbox" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "archived", label: "Archived" },
] as const;

type DocumentStatus = (typeof STATUS_OPTIONS)[number]["value"];

const STATUS_RANK: Record<Exclude<DocumentStatus, "all">, number> = {
  inbox: 0,
  processing: 1,
  completed: 2,
  failed: 3,
  archived: 4,
};

type DocumentAction = "retry" | "archive" | "delete";

interface ActionFeedback {
  readonly tone: "info" | "success" | "warning" | "danger";
  readonly message: string;
}

type DocumentSortField = "uploaded" | "name" | "status";
type DocumentSortDirection = "asc" | "desc";

interface DocumentSort {
  readonly field: DocumentSortField;
  readonly direction: DocumentSortDirection;
}

interface DocumentLastRun {
  readonly result: string;
  readonly timestamp: string | null;
}

interface DocumentViewModel extends WorkspaceDocumentSummary {
  readonly status: DocumentStatus;
  readonly source: string;
  readonly uploader: string;
  readonly tags: readonly string[];
  readonly fileType: string;
  readonly uploadedAtDate: Date;
  readonly lastRun: DocumentLastRun;
}

const STATUS_BADGES: Record<DocumentStatus, string> = {
  all: "bg-slate-100 text-slate-700",
  inbox: "bg-indigo-100 text-indigo-700",
  processing: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-danger-100 text-danger-700",
  archived: "bg-slate-200 text-slate-700",
};

const DEFAULT_SORT: DocumentSort = { field: "uploaded", direction: "desc" };

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const documentsQuery = useWorkspaceDocumentsQuery(workspace.id);
  const uploadDocumentsMutation = useUploadDocumentsMutation(workspace.id);
  const deleteDocumentsMutation = useDeleteDocumentsMutation(workspace.id);
  const [searchParams, setSearchParams] = useSearchParams();
  const { openInspector, closeInspector } = useWorkspaceChrome();

  const searchInputRef = useRef<HTMLInputElement>(null);
  const filterAnchorRef = useRef<HTMLButtonElement>(null);
  const connectAnchorRef = useRef<HTMLButtonElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const [filtersOpen, setFiltersOpen] = useState(false);
  const [connectMenuOpen, setConnectMenuOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);

  const rawStatus = (searchParams.get("status") ?? "all").toLowerCase();
  const status: DocumentStatus = STATUS_OPTIONS.some((option) => option.value === rawStatus)
    ? (rawStatus as DocumentStatus)
    : "all";
  const viewMode = searchParams.get("view") === "list" ? "list" : "grid";
  const searchQuery = searchParams.get("q") ?? "";
  const sortParam = searchParams.get("sort");
  const sort = useMemo(() => parseSort(sortParam), [sortParam]);
  const page = parsePage(searchParams.get("page"));
  const selectedDocumentId = searchParams.get("document");

  const filters = {
    source: sanitize(searchParams.get("source")),
    uploader: sanitize(searchParams.get("uploader")),
    tag: sanitize(searchParams.get("tag")),
    fileType: sanitize(searchParams.get("type")),
    from: sanitize(searchParams.get("from")),
    to: sanitize(searchParams.get("to")),
  };

  useEffect(() => {
    if (!actionFeedback || typeof window === "undefined") {
      return;
    }
    const timeout = window.setTimeout(() => setActionFeedback(null), 6000);
    return () => window.clearTimeout(timeout);
  }, [actionFeedback]);

  const documents = useMemo(() => {
    return (documentsQuery.data ?? []).map((document) => buildDocumentViewModel(document));
  }, [documentsQuery.data]);

  useEffect(() => {
    setSelectedIds((current) => {
      if (current.size === 0) {
        return current;
      }
      const next = new Set(Array.from(current).filter((id) => documents.some((document) => document.id === id)));
      if (next.size === current.size) {
        return current;
      }
      return next;
    });
  }, [documents]);

  const activeDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );

  const filteredDocuments = useMemo(() => {
    const fromDate = parseDateFilter(filters.from, "start");
    const toDate = parseDateFilter(filters.to, "end");
    const query = searchQuery.trim().toLowerCase();
    return documents.filter((document) => {
      if (status !== "all" && document.status !== status) {
        return false;
      }
      if (filters.source && document.source !== filters.source) {
        return false;
      }
      if (filters.uploader && document.uploader !== filters.uploader) {
        return false;
      }
      if (filters.fileType && document.fileType !== filters.fileType) {
        return false;
      }
      if (filters.tag && !document.tags.includes(filters.tag)) {
        return false;
      }
      if (fromDate && document.uploadedAtDate < fromDate) {
        return false;
      }
      if (toDate && document.uploadedAtDate > toDate) {
        return false;
      }
      if (query.length > 0) {
        const target = [document.name, document.source, document.uploader, ...document.tags]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!target.includes(query)) {
          return false;
        }
      }
      return true;
    });
  }, [documents, filters, searchQuery, status]);

  const sortedDocuments = useMemo(
    () => sortDocuments(filteredDocuments, sort),
    [filteredDocuments, sort],
  );

  const totalPages = Math.max(1, Math.ceil(sortedDocuments.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(page, 1), totalPages);

  useEffect(() => {
    if (safePage !== page) {
      setSearchParams((params) => {
        if (safePage === 1) {
          params.delete("page");
        } else {
          params.set("page", safePage.toString());
        }
        return params;
      });
    }
  }, [page, safePage, setSearchParams]);

  const pagedDocuments = useMemo(
    () =>
      sortedDocuments.slice(
        (safePage - 1) * PAGE_SIZE,
        (safePage - 1) * PAGE_SIZE + PAGE_SIZE,
      ),
    [safePage, sortedDocuments],
  );

  useEffect(() => {
    setSelectedIds(new Set());
  }, [safePage]);

  const statusCounts = useMemo(() => {
    const counts = new Map<DocumentStatus, number>();
    STATUS_OPTIONS.forEach((option) => counts.set(option.value, 0));
    counts.set("all", documents.length);
    for (const document of documents) {
      counts.set(document.status, (counts.get(document.status) ?? 0) + 1);
    }
    return counts;
  }, [documents]);

  const sourceOptions = useMemo(
    () => uniqueValues(documents.map((document) => document.source)),
    [documents],
  );
  const uploaderOptions = useMemo(
    () => uniqueValues(documents.map((document) => document.uploader)),
    [documents],
  );
  const tagOptions = useMemo(
    () => uniqueValues(documents.flatMap((document) => document.tags)),
    [documents],
  );
  const fileTypeOptions = useMemo(
    () => uniqueValues(documents.map((document) => document.fileType)),
    [documents],
  );

  const hasDocuments = documents.length > 0;
  const hasFilteredDocuments = filteredDocuments.length > 0;
  const filterCount = [filters.source, filters.uploader, filters.tag, filters.fileType, filters.from, filters.to]
    .filter((value) => Boolean(value && value.length > 0)).length;

  const isUploading = uploadDocumentsMutation.isPending;
  const isDeleting = deleteDocumentsMutation.isPending;

  const allSelected = pagedDocuments.length > 0 && pagedDocuments.every((document) => selectedIds.has(document.id));
  const someSelected = pagedDocuments.some((document) => selectedIds.has(document.id));
  const selectedCount = selectedIds.size;

  const openDocument = useCallback(
    (documentId: string) => {
      trackDocumentAction("open", workspace.id, documentId);
      setSearchParams((params) => {
        params.set("document", documentId);
        return params;
      });
    },
    [setSearchParams, workspace.id],
  );

  const notifyComingSoon = useCallback(
    (action: string, message: string, documentId?: string) => {
      trackDocumentAction(action, workspace.id, documentId);
      setActionFeedback({ tone: "info", message });
    },
    [workspace.id],
  );

  const handleToggleConnectMenu = useCallback(() => {
    trackDocumentAction("connect_source", workspace.id);
    setConnectMenuOpen((open) => !open);
  }, [workspace.id]);

  const handleUploadButton = useCallback(() => {
    setActionFeedback(null);
    if (connectMenuOpen) {
      setConnectMenuOpen(false);
    }
    trackDocumentAction("upload", workspace.id);
    uploadInputRef.current?.click();
  }, [connectMenuOpen, workspace.id, uploadInputRef]);

  const handleUploadInputChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const fileList = event.target.files;
      event.target.value = "";
      if (!fileList || fileList.length === 0) {
        return;
      }
      const files = Array.from(fileList);
      setActionFeedback(null);
      try {
        const uploaded = await uploadDocumentsMutation.mutateAsync({ files });
        setSelectedIds(new Set());
        setActiveDocumentId(null);
        if (uploaded.length === 1) {
          trackDocumentAction("upload", workspace.id, uploaded[0]?.id);
        } else {
          trackDocumentAction("bulk_upload", workspace.id);
        }
        const message =
          uploaded.length <= 1
            ? `${files[0]?.name ?? "Document"} uploaded.`
            : `${uploaded.length} documents uploaded.`;
        setActionFeedback({ tone: "success", message });
      } catch (error) {
        setActionFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to upload documents. Try again."),
        });
      }
    },
    [uploadDocumentsMutation, workspace.id],
  );

  const handleDeleteDocuments = useCallback(
    async (documentIds: readonly string[]) => {
      if (documentIds.length === 0) {
        return;
      }
      setActionFeedback(null);
      try {
        await deleteDocumentsMutation.mutateAsync(documentIds);
        setSelectedIds((current) => {
          const next = new Set(current);
          documentIds.forEach((id) => next.delete(id));
          return next;
        });
        setActiveDocumentId((current) => (current && documentIds.includes(current) ? null : current));
        if (selectedDocumentId && documentIds.includes(selectedDocumentId)) {
          clearDocumentSelection(setSearchParams);
        }
        const action = documentIds.length === 1 ? "delete" : "bulk_delete";
        trackDocumentAction(action, workspace.id, documentIds.length === 1 ? documentIds[0] : undefined);
        const message =
          documentIds.length === 1 ? "Document deleted." : `${documentIds.length} documents deleted.`;
        setActionFeedback({ tone: "success", message });
      } catch (error) {
        setActionFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to delete documents. Try again."),
        });
      }
    },
    [deleteDocumentsMutation, selectedDocumentId, setSearchParams, workspace.id],
  );

  const handleDocumentAction = useCallback(
    (document: DocumentViewModel, action: DocumentAction) => {
      switch (action) {
        case "retry":
          notifyComingSoon("retry", "Document reprocessing will be available soon.", document.id);
          break;
        case "archive":
          notifyComingSoon("archive", "Archiving is coming soon.", document.id);
          break;
        case "delete":
          void handleDeleteDocuments([document.id]);
          break;
      }
    },
    [handleDeleteDocuments, notifyComingSoon],
  );

  const handleBulkRetry = useCallback(() => {
    if (selectedCount === 0) {
      return;
    }
    notifyComingSoon("bulk_retry", "Bulk retry is coming soon.");
  }, [notifyComingSoon, selectedCount]);

  const handleBulkArchive = useCallback(() => {
    if (selectedCount === 0) {
      return;
    }
    notifyComingSoon("bulk_archive", "Bulk archive is coming soon.");
  }, [notifyComingSoon, selectedCount]);

  const handleBulkDelete = useCallback(() => {
    if (selectedCount === 0) {
      return;
    }
    void handleDeleteDocuments(Array.from(selectedIds));
  }, [handleDeleteDocuments, selectedCount, selectedIds]);

  const handleDownloadDocument = useCallback(
    (documentId: string) => {
      const downloadUrl = `/api/v1/workspaces/${workspace.id}/documents/${documentId}/download`;
      trackDocumentAction("download", workspace.id, documentId);
      if (typeof window !== "undefined") {
        window.open(downloadUrl, "_blank", "noopener");
      }
    },
    [workspace.id],
  );

  useEffect(() => {
    if (!selectedDocumentId) {
      closeInspector();
      return;
    }
    if (!activeDocument) {
      if (!documentsQuery.isLoading && !documentsQuery.isFetching) {
        clearDocumentSelection(setSearchParams);
      }
      return;
    }
    setActiveDocumentId(selectedDocumentId);
    const cleanup = () => clearDocumentSelection(setSearchParams);
    openInspector({
      title: activeDocument.name,
      content: (
        <DocumentInspector
          document={activeDocument}
          onRetry={() => notifyComingSoon("retry", "Document reprocessing will be available soon.", activeDocument.id)}
          onOpenRuns={() => notifyComingSoon("open_runs", "Run history will land in a future update.", activeDocument.id)}
          onDownload={() => handleDownloadDocument(activeDocument.id)}
        />
      ),
      onClose: cleanup,
    });
  }, [
    activeDocument,
    closeInspector,
    handleDownloadDocument,
    documentsQuery.isFetching,
    documentsQuery.isLoading,
    notifyComingSoon,
    openInspector,
    selectedDocumentId,
    setSearchParams,
    workspace.id,
  ]);

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "/" && !event.defaultPrevented) {
        const target = event.target as HTMLElement | null;
        if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
          return;
        }
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.key === "Enter" && !event.defaultPrevented && activeDocumentId) {
        if (!selectedDocumentId) {
          const exists = documents.some((document) => document.id === activeDocumentId);
          if (exists) {
            event.preventDefault();
            openDocument(activeDocumentId);
          }
        }
      }
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [activeDocumentId, documents, openDocument, selectedDocumentId]);

  const handleStatusChange = useCallback(
    (nextStatus: DocumentStatus) => {
      setActionFeedback(null);
      setSearchParams((params) => {
        params.set("status", nextStatus);
        params.delete("page");
        params.delete("document");
        return params;
      });
    },
    [setSearchParams],
  );

  const handleViewChange = useCallback(
    (nextView: "grid" | "list") => {
      setActionFeedback(null);
      setSearchParams((params) => {
        params.set("view", nextView);
        return params;
      });
    },
    [setSearchParams],
  );

  const handleSortChange = useCallback(
    (field: DocumentSortField) => {
      setActionFeedback(null);
      setSearchParams((params) => {
        const current = parseSort(params.get("sort"));
        const direction: DocumentSortDirection =
          current.field === field && current.direction === "desc" ? "asc" : "desc";
        const next = encodeSort({ field, direction });
        if (next === encodeSort(DEFAULT_SORT)) {
          params.delete("sort");
        } else {
          params.set("sort", next);
        }
        params.delete("page");
        return params;
      });
    },
    [setSearchParams],
  );

  const handleFilterChange = useCallback(
    (key: keyof typeof filters, value: string) => {
      setActionFeedback(null);
      setSearchParams((params) => {
        const paramKey = key === "fileType" ? "type" : key;
        if (value) {
          params.set(paramKey, value);
        } else {
          params.delete(paramKey);
        }
        params.delete("page");
        return params;
      });
    },
    [setSearchParams],
  );

  const handleDateFilterChange = useCallback(
    (key: "from" | "to", value: string) => {
      setActionFeedback(null);
      setSearchParams((params) => {
        if (value) {
          params.set(key, value);
        } else {
          params.delete(key);
        }
        params.delete("page");
        return params;
      });
    },
    [setSearchParams],
  );

  const handleClearFilters = useCallback(() => {
    setActionFeedback(null);
    setSearchParams((params) => {
      params.delete("source");
      params.delete("uploader");
      params.delete("tag");
      params.delete("type");
      params.delete("from");
      params.delete("to");
      params.delete("q");
      params.set("status", "all");
      params.delete("page");
      params.delete("document");
      params.delete("sort");
      return params;
    });
  }, [setSearchParams]);

  const handleSearchChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setActionFeedback(null);
      setSearchParams((params) => {
        if (value.trim().length > 0) {
          params.set("q", value);
        } else {
          params.delete("q");
        }
        params.delete("page");
        return params;
      });
    },
    [setSearchParams],
  );

  const handleSearchClear = useCallback(() => {
    setActionFeedback(null);
    setSearchParams((params) => {
      params.delete("q");
      params.delete("page");
      return params;
    });
  }, [setSearchParams]);

  const handleToggleSelection = useCallback((documentId: string, selected: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) {
        next.add(documentId);
      } else {
        next.delete(documentId);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(
    (checked: boolean) => {
      setSelectedIds((current) => {
        const next = new Set(current);
        for (const document of pagedDocuments) {
          if (checked) {
            next.add(document.id);
          } else {
            next.delete(document.id);
          }
        }
        return next;
      });
    },
    [pagedDocuments],
  );

  if (documentsQuery.isLoading) {
    return <PageState title="Loading documents" variant="loading" />;
  }

  if (documentsQuery.isError) {
    return (
      <PageState
        title="Unable to load documents"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => documentsQuery.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  const uploadInput = (
    <input
      ref={uploadInputRef}
      type="file"
      multiple
      accept=".pdf,.csv,.tsv,.xls,.xlsx,.xlsm,.xlsb"
      className="hidden"
      onChange={handleUploadInputChange}
    />
  );

  const feedbackBanner = actionFeedback ? (
    <ActionFeedbackBanner feedback={actionFeedback} onDismiss={() => setActionFeedback(null)} />
  ) : null;

  if (!hasDocuments) {
    return (
      <div className="space-y-6">
        {uploadInput}
        {feedbackBanner}
        <EmptyAllState
          onUpload={handleUploadButton}
          onConnectSource={handleToggleConnectMenu}
          connectMenuOpen={connectMenuOpen}
          onCloseConnectMenu={() => setConnectMenuOpen(false)}
          connectAnchorRef={connectAnchorRef}
          workspaceId={workspace.id}
          isUploadPending={isUploading}
        />
      </div>
    );
  }

  if (!hasFilteredDocuments) {
    return (
      <div className="space-y-6">
        {uploadInput}
        {feedbackBanner}
        <EmptyFilteredState onClearFilters={handleClearFilters} />
      </div>
    );
  }

  return (
    <section className="space-y-6">
      {uploadInput}
      {feedbackBanner}
      <header className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
            <p className="text-sm text-slate-500">
              Monitor uploads, track extraction progress, and jump into run details without leaving the workspace.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                ref={connectAnchorRef}
                type="button"
                variant="secondary"
                onClick={handleToggleConnectMenu}
                aria-haspopup="menu"
                aria-expanded={connectMenuOpen}
              >
                Connect source
                <CaretDownIcon />
              </Button>
              <ConnectSourceMenu
                open={connectMenuOpen}
                anchorRef={connectAnchorRef}
                onClose={() => setConnectMenuOpen(false)}
                workspaceId={workspace.id}
              />
            </div>
            <Button type="button" onClick={handleUploadButton} isLoading={isUploading}>
              Upload
            </Button>
          </div>
        </div>

        <StatusChips
          status={status}
          counts={statusCounts}
          onChange={(nextStatus) => {
            handleStatusChange(nextStatus);
            setActiveDocumentId(null);
          }}
        />

        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <SearchInput
              inputRef={searchInputRef}
              value={searchQuery}
              onChange={handleSearchChange}
              onClear={handleSearchClear}
            />
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                ref={filterAnchorRef}
                type="button"
                variant="secondary"
                onClick={() => setFiltersOpen((open) => !open)}
                aria-haspopup="dialog"
                aria-expanded={filtersOpen}
              >
                Filters
                {filterCount > 0 ? <FilterCountBadge count={filterCount} /> : null}
              </Button>
              <FiltersDropdown
                open={filtersOpen}
                anchorRef={filterAnchorRef}
                filters={filters}
                sourceOptions={sourceOptions}
                uploaderOptions={uploaderOptions}
                tagOptions={tagOptions}
                fileTypeOptions={fileTypeOptions}
                onChange={handleFilterChange}
                onChangeDate={handleDateFilterChange}
                onClear={handleClearFilters}
                onClose={() => setFiltersOpen(false)}
              />
            </div>
            <ViewToggle view={viewMode} onChange={handleViewChange} />
          </div>
        </div>
      </header>

      {viewMode === "grid" ? (
        <Fragment>
          <DocumentsGrid
            documents={pagedDocuments}
            sort={sort}
            onSortChange={handleSortChange}
            selectedIds={selectedIds}
            onToggleSelection={handleToggleSelection}
            onSelectAll={handleSelectAll}
            allSelected={allSelected}
            someSelected={someSelected}
            onOpenDocument={openDocument}
            onFocusDocument={setActiveDocumentId}
            activeDocumentId={activeDocumentId}
            selectedDocumentId={selectedDocumentId}
            onAction={handleDocumentAction}
            actionsDisabled={isDeleting}
            deletePending={isDeleting}
          />
          <DocumentsMobileList
            documents={pagedDocuments}
            selectedIds={selectedIds}
            onToggleSelection={handleToggleSelection}
            onOpenDocument={openDocument}
            onFocusDocument={setActiveDocumentId}
            selectedDocumentId={selectedDocumentId}
            onAction={handleDocumentAction}
            actionsDisabled={isDeleting}
            deletePending={isDeleting}
          />
        </Fragment>
      ) : (
        <Fragment>
          <DocumentsList
            documents={pagedDocuments}
            selectedIds={selectedIds}
            onToggleSelection={handleToggleSelection}
            onOpenDocument={openDocument}
            onFocusDocument={setActiveDocumentId}
            selectedDocumentId={selectedDocumentId}
            onAction={handleDocumentAction}
            actionsDisabled={isDeleting}
            deletePending={isDeleting}
          />
          <DocumentsMobileList
            documents={pagedDocuments}
            selectedIds={selectedIds}
            onToggleSelection={handleToggleSelection}
            onOpenDocument={openDocument}
            onFocusDocument={setActiveDocumentId}
            selectedDocumentId={selectedDocumentId}
            onAction={handleDocumentAction}
            actionsDisabled={isDeleting}
            deletePending={isDeleting}
          />
        </Fragment>
      )}

      <Pagination
        page={safePage}
        totalPages={totalPages}
        onChange={(nextPage) => {
          setSearchParams((params) => {
            if (nextPage <= 1) {
              params.delete("page");
            } else {
              params.set("page", nextPage.toString());
            }
            return params;
          });
        }}
      />

      {selectedCount > 0 ? (
        <BulkActionBar
          count={selectedCount}
          onRetry={handleBulkRetry}
          onArchive={handleBulkArchive}
          onDelete={handleBulkDelete}
          isProcessing={isDeleting}
        />
      ) : null}
    </section>
  );
}

function buildDocumentViewModel(document: WorkspaceDocumentSummary): DocumentViewModel {
  const metadata = document.metadata ?? {};
  const status = extractStatus(metadata);
  const source = extractString(metadata, ["source", "ingestSource"], "Manual upload");
  const uploader = extractString(metadata, ["uploader", "uploadedBy", "createdBy"], "Unknown");
  const tags = extractTags(metadata);
  const fileType = extractFileType(document, metadata);
  const uploadedAtDate = safeDate(document.createdAt ?? document.updatedAt ?? new Date().toISOString());
  const lastRun = extractLastRun(metadata);

  return {
    ...document,
    status,
    source,
    uploader,
    tags,
    fileType,
    uploadedAtDate,
    lastRun,
  };
}

function extractStatus(metadata: Record<string, unknown>): DocumentStatus {
  if (metadata.archived === true) {
    return "archived";
  }
  const rawStatus = extractString(metadata, ["status", "state"], "");
  switch (rawStatus.toLowerCase()) {
    case "inbox":
      return "inbox";
    case "processing":
    case "running":
      return "processing";
    case "failed":
    case "error":
      return "failed";
    case "archived":
      return "archived";
    case "completed":
    case "succeeded":
    case "success":
      return "completed";
    default:
      break;
  }
  if (metadata.processing === true) {
    return "processing";
  }
  if (metadata.failed === true) {
    return "failed";
  }
  return "completed";
}

function extractString(
  metadata: Record<string, unknown>,
  keys: readonly string[],
  fallback: string,
): string {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }
  return fallback;
}

function extractTags(metadata: Record<string, unknown>): readonly string[] {
  const raw = metadata.tags ?? metadata.labels;
  if (Array.isArray(raw)) {
    return raw
      .map((value) => (typeof value === "string" ? value.trim() : String(value)))
      .filter((value) => value.length > 0);
  }
  if (typeof raw === "string" && raw.trim().length > 0) {
    return raw
      .split(",")
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
  }
  return [];
}

function extractFileType(
  document: WorkspaceDocumentSummary,
  metadata: Record<string, unknown>,
): string {
  const fromMetadata = extractString(metadata, ["fileType", "file_type", "format"], "");
  if (fromMetadata) {
    return normaliseFileType(fromMetadata);
  }
  if (document.contentType) {
    const parts = document.contentType.split("/");
    const last = parts[parts.length - 1] ?? document.contentType;
    return normaliseFileType(last);
  }
  const extension = document.name.includes(".") ? document.name.split(".").pop() ?? "" : "";
  if (extension) {
    return normaliseFileType(extension);
  }
  return "Unknown";
}

function normaliseFileType(value: string) {
  return value.toUpperCase();
}

function extractLastRun(metadata: Record<string, unknown>): DocumentLastRun {
  const raw = (metadata.lastRun ?? metadata.last_run) as Record<string, unknown> | undefined;
  if (raw && typeof raw === "object") {
    const result = extractString(raw, ["result", "status", "outcome"], "Unknown");
    const timestampValue = raw.timestamp ?? raw.completedAt ?? raw.completed_at;
    const timestamp = typeof timestampValue === "string" ? timestampValue : null;
    return {
      result: capitalise(result),
      timestamp,
    };
  }
  return { result: "Not started", timestamp: null };
}

function capitalise(value: string) {
  if (value.length === 0) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function safeDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return new Date();
  }
  return date;
}

function parseSort(raw: string | null): DocumentSort {
  if (!raw) {
    return DEFAULT_SORT;
  }
  const [field, direction] = raw.split(":");
  const fieldValue: DocumentSortField = field === "name" || field === "status" ? (field as DocumentSortField) : "uploaded";
  const directionValue: DocumentSortDirection = direction === "asc" ? "asc" : "desc";
  return { field: fieldValue, direction: directionValue };
}

function encodeSort(sort: DocumentSort) {
  return `${sort.field}:${sort.direction}`;
}

function sortDocuments(documents: readonly DocumentViewModel[], sort: DocumentSort) {
  const multiplier = sort.direction === "asc" ? 1 : -1;
  const copy = [...documents];
  copy.sort((a, b) => {
    switch (sort.field) {
      case "name": {
        return multiplier * a.name.localeCompare(b.name);
      }
      case "status": {
        const rankA = STATUS_RANK[a.status as Exclude<DocumentStatus, "all">] ?? Number.MAX_SAFE_INTEGER;
        const rankB = STATUS_RANK[b.status as Exclude<DocumentStatus, "all">] ?? Number.MAX_SAFE_INTEGER;
        if (rankA !== rankB) {
          return multiplier * (rankA - rankB);
        }
        return multiplier * a.name.localeCompare(b.name);
      }
      case "uploaded":
      default: {
        return multiplier * (a.uploadedAtDate.getTime() - b.uploadedAtDate.getTime());
      }
    }
  });
  return copy;
}

function uniqueValues(values: readonly string[]) {
  return Array.from(new Set(values.filter((value) => value && value.length > 0))).sort((a, b) => a.localeCompare(b));
}

function sanitize(value: string | null) {
  if (!value) {
    return "";
  }
  return value.trim();
}

function resolveApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    return error.problem?.detail ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function parseDateFilter(value: string, boundary: "start" | "end") {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  if (boundary === "start") {
    date.setHours(0, 0, 0, 0);
  } else {
    date.setHours(23, 59, 59, 999);
  }
  return date;
}

function parsePage(value: string | null) {
  if (!value) {
    return 1;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return 1;
  }
  return parsed;
}

function clearDocumentSelection(setSearchParams: ReturnType<typeof useSearchParams>[1]) {
  setSearchParams((params) => {
    params.delete("document");
    return params;
  });
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not run";
  }
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatUploaded(date: Date) {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
  } catch {
    return date.toISOString();
  }
}

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "-";
  }
  if (bytes === 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / Math.pow(1024, index);
  return `${size.toFixed(1)} ${units[index]}`;
}

function trackDocumentAction(action: string, workspaceId: string, documentId?: string) {
  trackEvent({
    name: `documents.${action}`,
    payload: { workspaceId, documentId },
  });
}

interface StatusChipsProps {
  readonly status: DocumentStatus;
  readonly counts: Map<DocumentStatus, number>;
  readonly onChange: (status: DocumentStatus) => void;
}

function StatusChips({ status, counts, onChange }: StatusChipsProps) {
  return (
    <div className="flex flex-wrap gap-2" role="tablist" aria-label="Document status filters">
      {STATUS_OPTIONS.map((option) => {
        const isActive = status === option.value;
        const count = counts.get(option.value) ?? 0;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(option.value)}
            className={clsx(
              "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
              isActive
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:text-brand-700",
            )}
          >
            <span>{option.label}</span>
            <span className="text-xs text-slate-400" aria-hidden="true">
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function FilterCountBadge({ count }: { readonly count: number }) {
  return (
    <span className="ml-2 inline-flex min-w-[1.5rem] items-center justify-center rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-brand-700">
      {count}
    </span>
  );
}

interface SearchInputProps {
  readonly value: string;
  readonly onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  readonly onClear: () => void;
  readonly inputRef?: RefObject<HTMLInputElement | null>;
}

function SearchInput({ value, onChange, onClear, inputRef }: SearchInputProps) {
  return (
    <div className="relative">
      <Input
        ref={inputRef}
        type="search"
        value={value}
        onChange={onChange}
        placeholder="Search documents"
        className="pr-10"
      />
      {value.length > 0 ? (
        <button
          type="button"
          onClick={onClear}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 transition hover:text-brand-600 focus:outline-none"
          aria-label="Clear search"
        >
          <CloseIcon />
        </button>
      ) : null}
    </div>
  );
}

interface ViewToggleProps {
  readonly view: "grid" | "list";
  readonly onChange: (view: "grid" | "list") => void;
}

function ViewToggle({ view, onChange }: ViewToggleProps) {
  return (
    <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-1 text-xs font-semibold text-slate-600">
      <button
        type="button"
        onClick={() => onChange("grid")}
        className={clsx(
          "rounded-md px-3 py-1 transition",
          view === "grid" ? "bg-brand-600 text-white shadow-sm" : "hover:bg-slate-100",
        )}
        aria-pressed={view === "grid"}
      >
        Grid
      </button>
      <button
        type="button"
        onClick={() => onChange("list")}
        className={clsx(
          "rounded-md px-3 py-1 transition",
          view === "list" ? "bg-brand-600 text-white shadow-sm" : "hover:bg-slate-100",
        )}
        aria-pressed={view === "list"}
      >
        List
      </button>
    </div>
  );
}

interface FiltersDropdownProps {
  readonly open: boolean;
  readonly anchorRef: RefObject<HTMLButtonElement | null>;
  readonly filters: {
    readonly source: string;
    readonly uploader: string;
    readonly tag: string;
    readonly fileType: string;
    readonly from: string;
    readonly to: string;
  };
  readonly sourceOptions: readonly string[];
  readonly uploaderOptions: readonly string[];
  readonly tagOptions: readonly string[];
  readonly fileTypeOptions: readonly string[];
  readonly onChange: (key: "source" | "uploader" | "tag" | "fileType", value: string) => void;
  readonly onChangeDate: (key: "from" | "to", value: string) => void;
  readonly onClear: () => void;
  readonly onClose: () => void;
}

function FiltersDropdown({
  open,
  anchorRef,
  filters,
  sourceOptions,
  uploaderOptions,
  tagOptions,
  fileTypeOptions,
  onChange,
  onChangeDate,
  onClear,
  onClose,
}: FiltersDropdownProps) {
  const desktopPanelRef = useRef<HTMLDivElement>(null);
  const mobilePanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleClick(event: MouseEvent) {
      const target = event.target as Node;
      if (
        desktopPanelRef.current?.contains(target) ||
        mobilePanelRef.current?.contains(target) ||
        anchorRef.current?.contains(target as Node)
      ) {
        return;
      }
      onClose();
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [anchorRef, onClose, open]);

  if (!open) {
    return null;
  }

  const content = (
    <div className="space-y-4">
      <FilterSelect
        id="filter-source"
        label="Source"
        value={filters.source}
        onChange={(value) => onChange("source", value)}
        options={sourceOptions}
        placeholder="All sources"
      />
      <FilterSelect
        id="filter-uploader"
        label="Uploader"
        value={filters.uploader}
        onChange={(value) => onChange("uploader", value)}
        options={uploaderOptions}
        placeholder="All uploaders"
      />
      <FilterSelect
        id="filter-tag"
        label="Tag"
        value={filters.tag}
        onChange={(value) => onChange("tag", value)}
        options={tagOptions}
        placeholder="All tags"
      />
      <FilterSelect
        id="filter-type"
        label="File type"
        value={filters.fileType}
        onChange={(value) => onChange("fileType", value)}
        options={fileTypeOptions}
        placeholder="All file types"
      />
      <FilterDateField
        id="filter-from"
        label="From"
        value={filters.from}
        onChange={(value) => onChangeDate("from", value)}
      />
      <FilterDateField
        id="filter-to"
        label="To"
        value={filters.to}
        onChange={(value) => onChangeDate("to", value)}
      />
      <div className="flex justify-between gap-3">
        <Button type="button" variant="ghost" onClick={onClear}>
          Clear filters
        </Button>
        <Button type="button" variant="primary" onClick={onClose}>
          Done
        </Button>
      </div>
    </div>
  );

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm md:hidden"
        aria-hidden
        onClick={onClose}
      />
      <div
        ref={mobilePanelRef}
        className="fixed inset-x-0 bottom-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-2xl border border-slate-200 bg-white p-5 shadow-2xl md:hidden"
        role="dialog"
        aria-modal="true"
        aria-label="Filter documents"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Filters</h2>
          <button
            type="button"
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500"
            aria-label="Close filters"
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>
        {content}
      </div>
      <div
        ref={desktopPanelRef}
        className="absolute right-0 z-50 mt-2 hidden w-80 rounded-2xl border border-slate-200 bg-white p-5 shadow-xl md:block"
        role="dialog"
        aria-modal="true"
        aria-label="Filter documents"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Filters</h2>
          <button
            type="button"
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500"
            aria-label="Close filters"
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>
        {content}
      </div>
    </>
  );
}

interface FilterSelectProps {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly options: readonly string[];
  readonly placeholder: string;
}

function FilterSelect({ id, label, value, onChange, options, placeholder }: FilterSelectProps) {
  return (
    <label htmlFor={id} className="block space-y-1 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select
        id={id}
        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function FilterDateField({
  id,
  label,
  value,
  onChange,
}: {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
}) {
  return (
    <label htmlFor={id} className="block space-y-1 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        id={id}
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      />
    </label>
  );
}

interface ConnectSourceMenuProps {
  readonly open: boolean;
  readonly anchorRef: RefObject<HTMLButtonElement | null>;
  readonly onClose: () => void;
  readonly workspaceId: string;
}

function ConnectSourceMenu({ open, anchorRef, onClose, workspaceId }: ConnectSourceMenuProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleClick(event: MouseEvent) {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || anchorRef.current?.contains(target)) {
        return;
      }
      onClose();
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [anchorRef, onClose, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      ref={panelRef}
      className="absolute right-0 z-40 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl"
      role="menu"
      aria-label="Connect document source"
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Connect a source</p>
      <ul className="space-y-1" role="list">
        {[
          { id: "email", label: "Email inbox", description: "Automatically ingest forwarded attachments" },
          { id: "s3", label: "S3 bucket", description: "Sync files from object storage" },
          { id: "sharepoint", label: "SharePoint", description: "Pull uploads from team spaces" },
        ].map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className="w-full rounded-lg px-3 py-2 text-left text-sm text-slate-600 transition hover:bg-slate-100"
              onClick={() => {
                trackEvent({ name: "documents.connect_source", payload: { workspaceId, source: item.id } });
                onClose();
              }}
            >
              <div className="font-medium text-slate-900">{item.label} (coming soon)</div>
              <div className="text-xs text-slate-500">{item.description}</div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface DocumentsGridProps {
  readonly documents: readonly DocumentViewModel[];
  readonly sort: DocumentSort;
  readonly onSortChange: (field: DocumentSortField) => void;
  readonly selectedIds: Set<string>;
  readonly onToggleSelection: (documentId: string, selected: boolean) => void;
  readonly onSelectAll: (checked: boolean) => void;
  readonly allSelected: boolean;
  readonly someSelected: boolean;
  readonly onOpenDocument: (documentId: string) => void;
  readonly onFocusDocument: (documentId: string) => void;
  readonly activeDocumentId: string | null;
  readonly selectedDocumentId: string | null;
  readonly onAction: (document: DocumentViewModel, action: DocumentAction) => void;
  readonly actionsDisabled: boolean;
  readonly deletePending: boolean;
}

function DocumentsGrid({
  documents,
  sort,
  onSortChange,
  selectedIds,
  onToggleSelection,
  onSelectAll,
  allSelected,
  someSelected,
  onOpenDocument,
  onFocusDocument,
  activeDocumentId,
  selectedDocumentId,
  onAction,
  actionsDisabled,
  deletePending,
}: DocumentsGridProps) {
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected && !allSelected;
    }
  }, [allSelected, someSelected]);

  return (
    <div className="hidden overflow-hidden rounded-xl border border-slate-200 md:block">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="w-12 px-3 py-3">
              <input
                ref={selectAllRef}
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus-visible:ring-brand-500"
                checked={allSelected}
                onChange={(event) => onSelectAll(event.target.checked)}
                aria-label="Select all documents on this page"
                disabled={actionsDisabled}
              />
            </th>
            <SortableHeader label="Name" active={sort.field === "name"} direction={sort.direction} onClick={() => onSortChange("name")} />
            <SortableHeader label="Status" active={sort.field === "status"} direction={sort.direction} onClick={() => onSortChange("status")} />
            <th scope="col" className="px-4 py-3">Source</th>
            <SortableHeader label="Uploaded" active={sort.field === "uploaded"} direction={sort.direction} onClick={() => onSortChange("uploaded")} />
            <th scope="col" className="px-4 py-3">Last run</th>
            <th scope="col" className="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {documents.map((document) => {
            const isSelected = selectedIds.has(document.id);
            const isActive = activeDocumentId === document.id || selectedDocumentId === document.id;
            return (
              <tr
                key={document.id}
                className={clsx(
                  "group focus-within:bg-brand-50/40",
                  isActive ? "bg-brand-50/40" : "hover:bg-slate-50",
                )}
              >
                <td className="px-3 py-3">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300 text-brand-600 focus-visible:ring-brand-500"
                    checked={isSelected}
                    onChange={(event) => onToggleSelection(document.id, event.target.checked)}
                    aria-label={`Select ${document.name}`}
                    onFocus={() => onFocusDocument(document.id)}
                    disabled={actionsDisabled}
                  />
                </td>
                <td className="max-w-xs px-4 py-3">
                  <button
                    type="button"
                    className="text-sm font-semibold text-slate-800 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                    onClick={() => onOpenDocument(document.id)}
                    onFocus={() => onFocusDocument(document.id)}
                  >
                    {document.name}
                  </button>
                  <div className="text-xs text-slate-500">{document.fileType}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", STATUS_BADGES[document.status])}>
                    {capitalise(document.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600">{document.source}</td>
                <td className="px-4 py-3 text-slate-600">{formatUploaded(document.uploadedAtDate)}</td>
                <td className="px-4 py-3 text-slate-600">
                  <div className="flex flex-col">
                    <span className="font-medium text-slate-700">{document.lastRun.result}</span>
                    <span className="text-xs text-slate-500">{formatDateTime(document.lastRun.timestamp)}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <DocumentActionsMenu
                    documentId={document.id}
                    onOpenDetails={() => onOpenDocument(document.id)}
                    onAction={(action) => onAction(document, action)}
                    disabled={actionsDisabled}
                    isDeleting={deletePending}
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

interface DocumentsListProps {
  readonly documents: readonly DocumentViewModel[];
  readonly selectedIds: Set<string>;
  readonly onToggleSelection: (documentId: string, selected: boolean) => void;
  readonly onOpenDocument: (documentId: string) => void;
  readonly onFocusDocument: (documentId: string) => void;
  readonly selectedDocumentId: string | null;
  readonly onAction: (document: DocumentViewModel, action: DocumentAction) => void;
  readonly actionsDisabled: boolean;
  readonly deletePending: boolean;
}

function DocumentsList({
  documents,
  selectedIds,
  onToggleSelection,
  onOpenDocument,
  onFocusDocument,
  selectedDocumentId,
  onAction,
  actionsDisabled,
  deletePending,
}: DocumentsListProps) {
  return (
    <div className="hidden space-y-3 md:block">
      {documents.map((document) => {
        const isSelected = selectedIds.has(document.id);
        const isActive = selectedDocumentId === document.id;
        return (
          <div
            key={document.id}
            className={clsx(
              "rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-200 hover:shadow-md",
              isActive && "border-brand-300 ring-1 ring-brand-200",
            )}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus-visible:ring-brand-500"
                  checked={isSelected}
                  onChange={(event) => onToggleSelection(document.id, event.target.checked)}
                  aria-label={`Select ${document.name}`}
                  disabled={actionsDisabled}
                />
                <div>
                  <button
                    type="button"
                    className="text-lg font-semibold text-slate-900 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                    onClick={() => onOpenDocument(document.id)}
                    onFocus={() => onFocusDocument(document.id)}
                  >
                    {document.name}
                  </button>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>{document.fileType}</span>
                    <span aria-hidden className="text-slate-300">
                      •
                    </span>
                    <span>{document.source}</span>
                    {document.tags.length > 0 ? (
                      <>
                        <span aria-hidden className="text-slate-300">
                          •
                        </span>
                        <span>{document.tags.join(", ")}</span>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>
              <DocumentActionsMenu
                documentId={document.id}
                onOpenDetails={() => onOpenDocument(document.id)}
                onAction={(action) => onAction(document, action)}
                disabled={actionsDisabled}
                isDeleting={deletePending}
              />
            </div>
            <dl className="mt-4 grid gap-4 text-sm text-slate-600 md:grid-cols-4">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</dt>
                <dd>
                  <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", STATUS_BADGES[document.status])}>
                    {capitalise(document.status)}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Uploaded</dt>
                <dd>{formatUploaded(document.uploadedAtDate)}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Last run</dt>
                <dd>
                  <div className="font-medium text-slate-700">{document.lastRun.result}</div>
                  <div className="text-xs text-slate-500">{formatDateTime(document.lastRun.timestamp)}</div>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Size</dt>
                <dd>{formatFileSize(document.byteSize)}</dd>
              </div>
            </dl>
          </div>
        );
      })}
    </div>
  );
}

interface DocumentsMobileListProps {
  readonly documents: readonly DocumentViewModel[];
  readonly selectedIds: Set<string>;
  readonly onToggleSelection: (documentId: string, selected: boolean) => void;
  readonly onOpenDocument: (documentId: string) => void;
  readonly onFocusDocument: (documentId: string) => void;
  readonly selectedDocumentId: string | null;
  readonly onAction: (document: DocumentViewModel, action: DocumentAction) => void;
  readonly actionsDisabled: boolean;
  readonly deletePending: boolean;
}

function DocumentsMobileList({
  documents,
  selectedIds,
  onToggleSelection,
  onOpenDocument,
  onFocusDocument,
  selectedDocumentId,
  onAction,
  actionsDisabled,
  deletePending,
}: DocumentsMobileListProps) {
  return (
    <div className="space-y-3 md:hidden">
      {documents.map((document) => {
        const isSelected = selectedIds.has(document.id);
        const isActive = selectedDocumentId === document.id;
        return (
          <div
            key={document.id}
            className={clsx(
              "rounded-xl border border-slate-200 bg-white p-4 shadow-sm",
              isActive && "border-brand-300",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus-visible:ring-brand-500"
                  checked={isSelected}
                  onChange={(event) => onToggleSelection(document.id, event.target.checked)}
                  aria-label={`Select ${document.name}`}
                  disabled={actionsDisabled}
                />
                <div>
                  <button
                    type="button"
                    className="text-base font-semibold text-slate-900 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                    onClick={() => onOpenDocument(document.id)}
                    onFocus={() => onFocusDocument(document.id)}
                  >
                    {document.name}
                  </button>
                  <div className="mt-1 text-xs text-slate-500">
                    {document.fileType} • {document.source}
                  </div>
                </div>
              </div>
              <DocumentActionsMenu
                documentId={document.id}
                onOpenDetails={() => onOpenDocument(document.id)}
                onAction={(action) => onAction(document, action)}
                disabled={actionsDisabled}
                isDeleting={deletePending}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
              <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 font-semibold", STATUS_BADGES[document.status])}>
                {capitalise(document.status)}
              </span>
              <span>Uploaded {formatUploaded(document.uploadedAtDate)}</span>
              <span>•</span>
              <span>{document.lastRun.result}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface SortableHeaderProps {
  readonly label: string;
  readonly active: boolean;
  readonly direction: DocumentSortDirection;
  readonly onClick: () => void;
}

function SortableHeader({ label, active, direction, onClick }: SortableHeaderProps) {
  return (
    <th scope="col" className="px-4 py-3">
      <button
        type="button"
        onClick={onClick}
        className={clsx(
          "inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide",
          active ? "text-brand-700" : "text-slate-500 hover:text-brand-600",
        )}
      >
        {label}
        <span aria-hidden className="text-slate-400">
          {active ? (direction === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  );
}

interface DocumentActionsMenuProps {
  readonly documentId: string;
  readonly onOpenDetails: () => void;
  readonly onAction: (action: DocumentAction) => void;
  readonly disabled?: boolean;
  readonly isDeleting?: boolean;
}

function DocumentActionsMenu({
  documentId,
  onOpenDetails,
  onAction,
  disabled = false,
  isDeleting = false,
}: DocumentActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleClick(event: MouseEvent) {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || anchorRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className="relative inline-flex">
      <button
        ref={anchorRef}
        type="button"
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-brand-200 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          if (disabled) {
            return;
          }
          setOpen((current) => !current);
        }}
        disabled={disabled}
        aria-label={`Open actions for document ${documentId}`}
      >
        <DotsIcon />
      </button>
      {open ? (
        <div
          ref={panelRef}
          className="absolute right-0 z-50 mt-2 w-48 rounded-xl border border-slate-200 bg-white p-2 text-sm text-slate-600 shadow-xl"
          role="menu"
        >
          <MenuButton
            label="Open details"
            onClick={() => {
              onOpenDetails();
              setOpen(false);
            }}
          />
          <MenuButton
            label="Start / retry extraction"
            onClick={() => {
              onAction("retry");
              setOpen(false);
            }}
            disabled={disabled}
          />
          <MenuButton
            label="Archive"
            onClick={() => {
              onAction("archive");
              setOpen(false);
            }}
            disabled={disabled}
          />
          <MenuButton
            label="Delete"
            tone="danger"
            onClick={() => {
              onAction("delete");
              setOpen(false);
            }}
            disabled={disabled}
            loading={isDeleting}
          />
        </div>
      ) : null}
    </div>
  );
}

function MenuButton({
  label,
  onClick,
  tone = "default",
  disabled = false,
  loading = false,
}: {
  readonly label: string;
  readonly onClick: () => void;
  readonly tone?: "default" | "danger";
  readonly disabled?: boolean;
  readonly loading?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={clsx(
        "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
        tone === "danger"
          ? "text-danger-600 hover:bg-danger-50"
          : "text-slate-600 hover:bg-slate-100",
      )}
      role="menuitem"
    >
      <span>{label}</span>
      {loading ? (
        <span
          aria-hidden
          className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      ) : null}
    </button>
  );
}

interface PaginationProps {
  readonly page: number;
  readonly totalPages: number;
  readonly onChange: (page: number) => void;
}

function Pagination({ page, totalPages, onChange }: PaginationProps) {
  if (totalPages <= 1) {
    return null;
  }
  const previousDisabled = page <= 1;
  const nextDisabled = page >= totalPages;
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
      <div>
        Page {page} of {totalPages}
      </div>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={previousDisabled}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={nextDisabled}
          onClick={() => onChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

interface BulkActionBarProps {
  readonly count: number;
  readonly onRetry: () => void;
  readonly onArchive: () => void;
  readonly onDelete: () => void;
  readonly isProcessing?: boolean;
}

function BulkActionBar({ count, onRetry, onArchive, onDelete, isProcessing = false }: BulkActionBarProps) {
  return (
    <div className="sticky bottom-4 flex items-center justify-between gap-3 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm text-slate-700 shadow-lg">
      <div className="font-semibold">{count} selected</div>
      <div className="flex items-center gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={onRetry} disabled={isProcessing}>
          Retry
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={onArchive} disabled={isProcessing}>
          Archive
        </Button>
        <Button type="button" variant="danger" size="sm" onClick={onDelete} isLoading={isProcessing}>
          Delete
        </Button>
      </div>
    </div>
  );
}

function ActionFeedbackBanner({
  feedback,
  onDismiss,
}: {
  readonly feedback: ActionFeedback;
  readonly onDismiss: () => void;
}) {
  return (
    <div className="relative">
      <Alert tone={feedback.tone} className="pr-12">
        {feedback.message}
      </Alert>
      <button
        type="button"
        className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 transition hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        aria-label="Dismiss message"
        onClick={onDismiss}
      >
        <CloseIcon />
      </button>
    </div>
  );
}

function EmptyAllState({
  onUpload,
  onConnectSource,
  connectMenuOpen,
  onCloseConnectMenu,
  connectAnchorRef,
  workspaceId,
  isUploadPending,
}: {
  readonly onUpload: () => void;
  readonly onConnectSource: () => void;
  readonly connectMenuOpen: boolean;
  readonly onCloseConnectMenu: () => void;
  readonly connectAnchorRef: RefObject<HTMLButtonElement | null>;
  readonly workspaceId: string;
  readonly isUploadPending: boolean;
}) {
  return (
    <section className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold text-slate-900">Upload your first spreadsheet or PDF</h1>
        <p className="text-sm text-slate-500">
          Kick off extraction by uploading files directly or connecting an automated source.
        </p>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Button type="button" onClick={onUpload} isLoading={isUploadPending}>
          Upload
        </Button>
        <div className="relative">
          <Button
            ref={connectAnchorRef}
            type="button"
            variant="secondary"
            onClick={onConnectSource}
            aria-haspopup="menu"
            aria-expanded={connectMenuOpen}
          >
            Connect source
            <CaretDownIcon />
          </Button>
          <ConnectSourceMenu
            open={connectMenuOpen}
            anchorRef={connectAnchorRef}
            onClose={onCloseConnectMenu}
            workspaceId={workspaceId}
          />
        </div>
      </div>
      <div className="mt-6 w-full max-w-xl rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-5 text-sm text-slate-500">
        Drag and drop files here to upload automatically.
      </div>
    </section>
  );
}

function EmptyFilteredState({ onClearFilters }: { readonly onClearFilters: () => void }) {
  return (
    <section className="flex flex-col items-center justify-center rounded-3xl border border-slate-200 bg-white px-6 py-16 text-center">
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold text-slate-900">No documents match these filters</h1>
        <p className="text-sm text-slate-500">Try adjusting your filters or widening the date range.</p>
      </div>
      <Button type="button" variant="secondary" className="mt-6" onClick={onClearFilters}>
        Clear filters
      </Button>
    </section>
  );
}

function DocumentInspector({
  document,
  onRetry,
  onOpenRuns,
  onDownload,
}: {
  readonly document: DocumentViewModel;
  readonly onRetry: () => void;
  readonly onOpenRuns: () => void;
  readonly onDownload: () => void;
}) {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h3 className="text-lg font-semibold text-slate-900">{document.name}</h3>
        <p className="text-sm text-slate-500">{document.fileType}</p>
      </header>
      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Preview</h4>
        <div className="flex h-40 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-400">
          Preview coming soon
        </div>
      </section>
      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metadata</h4>
        <dl className="divide-y divide-slate-200 rounded-xl border border-slate-200">
          <InspectorRow label="Status">
            <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", STATUS_BADGES[document.status])}>
              {capitalise(document.status)}
            </span>
          </InspectorRow>
          <InspectorRow label="Source">{document.source}</InspectorRow>
          <InspectorRow label="Uploader">{document.uploader}</InspectorRow>
          <InspectorRow label="Uploaded">{formatUploaded(document.uploadedAtDate)}</InspectorRow>
          <InspectorRow label="Size">{formatFileSize(document.byteSize)}</InspectorRow>
        </dl>
      </section>
      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Last run</h4>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <div className="font-semibold text-slate-800">{document.lastRun.result}</div>
          <div className="text-xs text-slate-500">{formatDateTime(document.lastRun.timestamp)}</div>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
          <Button type="button" variant="ghost" onClick={onDownload}>
            Download
          </Button>
          <Button type="button" variant="primary" onClick={onOpenRuns}>
            Open in Runs
          </Button>
        </div>
      </section>
      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Raw metadata</h4>
        <pre className="max-h-48 overflow-auto rounded-xl border border-slate-200 bg-slate-900/90 p-3 text-xs text-slate-100">
          {JSON.stringify(document.metadata, null, 2)}
        </pre>
      </section>
    </div>
  );
}

function InspectorRow({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 text-sm text-slate-600">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

function CaretDownIcon() {
  return (
    <svg className="ml-2 h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
      <path d="M5 5l10 10M15 5l-10 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <circle cx="4" cy="10" r="1.5" />
      <circle cx="10" cy="10" r="1.5" />
      <circle cx="16" cy="10" r="1.5" />
    </svg>
  );
}

