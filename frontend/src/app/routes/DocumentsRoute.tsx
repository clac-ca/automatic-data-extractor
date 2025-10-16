import { useCallback, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import clsx from "clsx";

import { useDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import { useUploadDocumentsMutation } from "../../features/documents/hooks/useUploadDocumentsMutation";
import { useDeleteDocumentsMutation } from "../../features/documents/hooks/useDeleteDocumentsMutation";
import { downloadWorkspaceDocument } from "../../features/documents/api";
import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { Alert, Button } from "../../ui";
import {
  SUPPORTED_FILE_EXTENSIONS,
  SUPPORTED_FILE_TYPES_LABEL,
  resolveApiErrorMessage,
  splitSupportedFiles,
  toDocumentRows,
  toSortParam,
  trackDocumentsEvent,
  triggerBrowserDownload,
  parseSortParam,
  type DocumentRow,
  type SortColumn,
  type SortState,
  type SplitFilesResult,
  type UploaderFilterValue,
} from "./documents/utils";
import { DocumentsToolbar } from "./documents/components/DocumentsToolbar";
import { DocumentsTable } from "./documents/components/DocumentsTable";
import { DocumentsEmptyState } from "./documents/components/DocumentsEmptyState";
import { DocumentDetails } from "./documents/components/DocumentDetails";
import { useDocumentsParams, DEFAULT_SORT_PARAM } from "./documents/hooks/useDocumentsParams";

function nextSort(column: SortColumn, current: SortState): SortState {
  if (current.column !== column) {
    const defaultDirection = column === "uploadedAt" || column === "lastRunAt" || column === "byteSize" ? "desc" : "asc";
    return { column, direction: defaultDirection };
  }
  return { column, direction: current.direction === "asc" ? "desc" : "asc" };
}

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const { openInspector } = useWorkspaceChrome();

  const documentsParams = useDocumentsParams();
  const {
    urlState,
    apiParams,
    setStatuses,
    addTag,
    removeTag,
    setUploader,
    setSearch,
    setSort,
    setPage,
    setPerPage,
    setCreatedRange,
    setLastRunRange,
    clearFilters,
  } = documentsParams;

  const documentsQuery = useDocumentsQuery(workspace.id, apiParams);
  const uploadDocuments = useUploadDocumentsMutation(workspace.id);
  const deleteDocuments = useDeleteDocumentsMutation(workspace.id);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [feedback, setFeedback] = useState<{ tone: "info" | "success" | "warning" | "danger"; message: string } | null>(
    null,
  );
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragDepth, setDragDepth] = useState(0);

  const sortState = useMemo(() => parseSortParam(urlState.sort), [urlState.sort]);
  const rows: DocumentRow[] = useMemo(
    () => toDocumentRows(documentsQuery.data?.items),
    [documentsQuery.data?.items],
  );

  const availableTags = useMemo(() => {
    const tagSet = new Set<string>();
    for (const record of documentsQuery.data?.items ?? []) {
      for (const tag of record.tags ?? []) {
        tagSet.add(tag);
      }
    }
    return Array.from(tagSet).sort((a, b) => a.localeCompare(b));
  }, [documentsQuery.data?.items]);

  const isLoading = documentsQuery.isLoading;
  const hasNext = documentsQuery.data?.has_next ?? false;
  const noDocumentsExist = Boolean(
    documentsQuery.data &&
      documentsQuery.data.page === 1 &&
      documentsQuery.data.items.length === 0 &&
      !documentsQuery.data.has_next,
  );
  const hasDocuments = !noDocumentsExist;
  const hasActiveFilters =
    urlState.status.length > 0 ||
    urlState.tags.length > 0 ||
    urlState.uploader === "me" ||
    urlState.q.trim().length > 0 ||
    Boolean(urlState.createdFrom) ||
    Boolean(urlState.createdTo) ||
    Boolean(urlState.lastRunFrom) ||
    Boolean(urlState.lastRunTo) ||
    urlState.sort !== DEFAULT_SORT_PARAM ||
    urlState.perPage !== 50 ||
    urlState.page !== 1;

  const containsFiles = useCallback((event: DragEvent<HTMLDivElement>) => {
    const { dataTransfer } = event;
    if (!dataTransfer) {
      return false;
    }
    if (dataTransfer.files && dataTransfer.files.length > 0) {
      return true;
    }
    const types = dataTransfer.types;
    return !!types && Array.from(types).includes("Files");
  }, []);

  const showFeedback = useCallback(
    (value: { tone: "info" | "success" | "warning" | "danger"; message: string }) => setFeedback(value),
    [],
  );
  const clearFeedback = useCallback(() => setFeedback(null), []);

  const handleSortChange = useCallback(
    (column: SortColumn) => {
      const next = nextSort(column, sortState);
      setSort(toSortParam(next));
      trackDocumentsEvent("sort", workspace.id, { column: next.column, direction: next.direction });
    },
    [sortState, setSort, workspace.id],
  );

  const handleUploaderChange = useCallback(
    (value: UploaderFilterValue) => {
      setUploader(value === "me" ? "me" : null);
      trackDocumentsEvent("filter_owner", workspace.id, { owner: value });
    },
    [setUploader, workspace.id],
  );

  const handleStatusesChange = useCallback(
    (values: string[]) => {
      setStatuses(values);
      trackDocumentsEvent("filter_status", workspace.id, { statuses: values });
    },
    [setStatuses, workspace.id],
  );

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearch(value);
      trackDocumentsEvent("filter_search", workspace.id, { value });
    },
    [setSearch, workspace.id],
  );

  const handleAddTag = useCallback(
    (tag: string) => {
      addTag(tag);
      trackDocumentsEvent("filter_tag_add", workspace.id, { tag });
    },
    [addTag, workspace.id],
  );

  const handleRemoveTag = useCallback(
    (tag: string) => {
      removeTag(tag);
      trackDocumentsEvent("filter_tag_remove", workspace.id, { tag });
    },
    [removeTag, workspace.id],
  );

  const handleInspect = useCallback(
    (document: DocumentRow) => {
      openInspector({ title: document.name, content: <DocumentDetails document={document} /> });
      trackDocumentsEvent("view_details", workspace.id, { documentId: document.id });
    },
    [openInspector, workspace.id],
  );

  const handleDownload = useCallback(
    async (document: DocumentRow) => {
      setDownloadingId(document.id);
      try {
        trackDocumentsEvent("download", workspace.id, { documentId: document.id });
        const { blob, filename } = await downloadWorkspaceDocument(workspace.id, document.id);
        triggerBrowserDownload(blob, filename ?? document.name);
      } catch (error) {
        showFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to download document."),
        });
      } finally {
        setDownloadingId(null);
      }
    },
    [showFeedback, workspace.id],
  );

  const handleDelete = useCallback(
    async (document: DocumentRow) => {
      setDeletingId(document.id);
      try {
        trackDocumentsEvent("delete", workspace.id, { documentId: document.id });
        await deleteDocuments.mutateAsync([document.id]);
        showFeedback({ tone: "success", message: "Document deleted." });
      } catch (error) {
        showFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to delete document. Try again."),
        });
      } finally {
        setDeletingId(null);
      }
    },
    [deleteDocuments, showFeedback, workspace.id],
  );

  const handleFilesSelected = useCallback(
    async (files: readonly File[]) => {
      if (!files.length) {
        return;
      }

      const { accepted, rejected }: SplitFilesResult = splitSupportedFiles(files);
      if (accepted.length === 0) {
        showFeedback({
          tone: "warning",
          message: `No supported files detected. Supported types: ${SUPPORTED_FILE_TYPES_LABEL}.`,
        });
        return;
      }

      clearFeedback();

      try {
        await uploadDocuments.mutateAsync({ files: accepted });
        if (rejected.length > 0) {
          showFeedback({
            tone: "warning",
            message: `${rejected.length} file${rejected.length === 1 ? " was" : "s were"} skipped because the format is not supported.`,
          });
        } else {
          showFeedback({ tone: "success", message: "Upload started." });
        }
        trackDocumentsEvent("upload", workspace.id, {
          accepted: accepted.length,
          rejected: rejected.length,
        });
      } catch (error) {
        showFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to upload documents. Try again."),
        });
      }
    },
    [clearFeedback, showFeedback, uploadDocuments, workspace.id],
  );

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files ? Array.from(event.target.files) : [];
      void handleFilesSelected(files);
      event.target.value = "";
    },
    [handleFilesSelected],
  );

  const handleDragEnter = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (!containsFiles(event)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setDragDepth((value) => value + 1);
    },
    [containsFiles],
  );

  const handleDragLeave = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (!containsFiles(event) && dragDepth === 0) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const nextTarget = event.relatedTarget as Node | null;
      if (nextTarget && event.currentTarget.contains(nextTarget)) {
        return;
      }
      setDragDepth((value) => Math.max(0, value - 1));
    },
    [containsFiles, dragDepth],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (!containsFiles(event)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setDragDepth(0);
      const files = event.dataTransfer?.files ? Array.from(event.dataTransfer.files) : [];
      void handleFilesSelected(files);
    },
    [containsFiles, handleFilesSelected],
  );

  const isDragging = dragDepth > 0;
  const showEmptyState = !isLoading && rows.length === 0;
  const uploaderFilter = urlState.uploader === "me" ? "me" : "all";

  return (
    <div className="flex h-full flex-col">
      <DocumentsToolbar
        uploader={uploaderFilter}
        onUploaderChange={handleUploaderChange}
        statuses={urlState.status}
        onStatusesChange={handleStatusesChange}
        tags={urlState.tags}
        onAddTag={handleAddTag}
        onRemoveTag={handleRemoveTag}
        availableTags={availableTags}
        createdFrom={urlState.createdFrom}
        createdTo={urlState.createdTo}
        onCreatedRangeChange={setCreatedRange}
        lastRunFrom={urlState.lastRunFrom}
        lastRunTo={urlState.lastRunTo}
        onLastRunRangeChange={setLastRunRange}
        search={urlState.q}
        onSearchChange={handleSearchChange}
        onClearFilters={clearFilters}
        onUploadClick={() => fileInputRef.current?.click()}
        isUploading={uploadDocuments.isPending}
        itemCount={rows.length}
        page={urlState.page}
        perPage={urlState.perPage}
        onPerPageChange={setPerPage}
        canClearFilters={hasActiveFilters}
      />

      <div
        className={clsx(
          "relative flex-1",
          isDragging ? "ring-2 ring-dashed ring-brand-500" : "",
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onDragOver={(event) => {
          if (containsFiles(event)) {
            event.preventDefault();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={SUPPORTED_FILE_EXTENSIONS.join(",")}
          className="hidden"
          onChange={handleFileInputChange}
        />

        {feedback ? (
          <div className="border-b border-slate-200 bg-slate-50 px-5 py-3">
            <Alert tone={feedback.tone}>
              <div className="flex items-start justify-between gap-3">
                <span>{feedback.message}</span>
                <button
                  type="button"
                  onClick={clearFeedback}
                  className="text-xs font-semibold uppercase tracking-wide text-slate-500 transition hover:text-slate-700"
                >
                  Dismiss
                </button>
              </div>
            </Alert>
          </div>
        ) : null}

        {showEmptyState ? (
          <DocumentsEmptyState
            hasDocuments={hasDocuments}
            hasActiveFilters={hasActiveFilters}
            onClearFilters={clearFilters}
            onUpload={() => fileInputRef.current?.click()}
            isUploading={uploadDocuments.isPending}
          />
        ) : (
          <>
            <DocumentsTable
              rows={rows}
              sortState={sortState}
              onSortChange={handleSortChange}
              onInspect={handleInspect}
              onDownload={handleDownload}
              onDelete={handleDelete}
              downloadingId={downloadingId}
              deletingId={deletingId}
              isLoading={isLoading}
            />
            <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-sm text-slate-600">
              <span>Page {urlState.page}</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(Math.max(1, urlState.page - 1))}
                  disabled={urlState.page === 1 || documentsQuery.isLoading}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(urlState.page + 1)}
                  disabled={!hasNext || documentsQuery.isLoading}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}

        {isDragging ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-white/80">
            <div className="rounded-lg border-2 border-dashed border-brand-500 bg-white px-6 py-4 text-center text-sm font-semibold text-brand-600 shadow-sm">
              Drop files to upload
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
