import { useCallback, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import clsx from "clsx";

import { useSession } from "../../features/auth/context/SessionContext";
import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import { useUploadDocumentsMutation } from "../../features/documents/hooks/useUploadDocumentsMutation";
import { useDeleteDocumentsMutation } from "../../features/documents/hooks/useDeleteDocumentsMutation";
import { downloadWorkspaceDocument } from "../../features/documents/api";
import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { PageState } from "../components/PageState";
import { Alert, Button } from "../../ui";
import {
  DEFAULT_SORT_STATE,
  SUPPORTED_FILE_EXTENSIONS,
  SUPPORTED_FILE_TYPES_LABEL,
  applyDocumentFilters,
  resolveApiErrorMessage,
  sortDocumentRows,
  splitSupportedFiles,
  toDocumentRows,
  toggleSort,
  trackDocumentsEvent,
  triggerBrowserDownload,
} from "./documents/utils";
import type { DocumentRow, OwnerFilterValue, SortColumn, SortState, StatusFilterValue } from "./documents/utils";
import { DocumentsToolbar } from "./documents/components/DocumentsToolbar";
import { DocumentsTable } from "./documents/components/DocumentsTable";
import { DocumentsEmptyState } from "./documents/components/DocumentsEmptyState";
import { DocumentDetails } from "./documents/components/DocumentDetails";

type FeedbackTone = "info" | "success" | "warning" | "danger";
interface FeedbackState {
  readonly tone: FeedbackTone;
  readonly message: string;
}

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const { user: currentUser } = useSession();
  const { openInspector } = useWorkspaceChrome();

  const documentsQuery = useWorkspaceDocumentsQuery(workspace.id);
  const uploadDocuments = useUploadDocumentsMutation(workspace.id);
  const deleteDocuments = useDeleteDocumentsMutation(workspace.id);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [ownerFilter, setOwnerFilter] = useState<OwnerFilterValue>("mine");
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortState, setSortState] = useState<SortState>(DEFAULT_SORT_STATE);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragDepth, setDragDepth] = useState(0);

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

  const documents = useMemo(() => toDocumentRows(documentsQuery.data), [documentsQuery.data]);
  const filteredDocuments = useMemo(
    () =>
      applyDocumentFilters(documents, {
        owner: ownerFilter,
        status: statusFilter,
        search: searchTerm,
        currentUser,
      }),
    [documents, ownerFilter, statusFilter, searchTerm, currentUser],
  );
  const visibleDocuments = useMemo(
    () => sortDocumentRows(filteredDocuments, sortState),
    [filteredDocuments, sortState],
  );

  const totalCount = documents.length;
  const resultCount = visibleDocuments.length;
  const hasDocuments = totalCount > 0;
  const hasVisibleDocuments = resultCount > 0;
  const isDragging = dragDepth > 0;

  const clearFeedback = useCallback(() => setFeedback(null), []);
  const showFeedback = useCallback((value: FeedbackState) => setFeedback(value), []);

  const handleSortChange = useCallback(
    (column: SortColumn) => {
      setSortState((current) => {
        const next = toggleSort(column, current);
        trackDocumentsEvent("sort", workspace.id, { column: next.column, direction: next.direction });
        return next;
      });
    },
    [workspace.id],
  );

  const handleOwnerChange = useCallback(
    (value: OwnerFilterValue) => {
      setOwnerFilter(value);
      trackDocumentsEvent("filter_owner", workspace.id, { owner: value });
    },
    [workspace.id],
  );

  const handleStatusChange = useCallback(
    (value: StatusFilterValue) => {
      setStatusFilter(value);
      trackDocumentsEvent("filter_status", workspace.id, { status: value });
    },
    [workspace.id],
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

      const { accepted, rejected } = splitSupportedFiles(files);
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

  const handleDragOver = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (!containsFiles(event) && dragDepth === 0) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "copy";
      }
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

  const openFileDialog = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUploadClick = useCallback(() => {
    trackDocumentsEvent("upload_click", workspace.id);
    openFileDialog();
  }, [openFileDialog, workspace.id]);

  if (documentsQuery.isLoading) {
    return <PageState title="Loading documents" description="Fetching workspace documents." variant="loading" />;
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

  return (
    <section className="flex h-full flex-col gap-3">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={SUPPORTED_FILE_EXTENSIONS.join(",")}
        className="hidden"
        onChange={handleFileInputChange}
      />

      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <div
        role="region"
        aria-label="Workspace documents"
        aria-busy={documentsQuery.isFetching}
        className={clsx(
          "relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-soft transition",
          isDragging ? "border-dashed border-brand-400 ring-4 ring-brand-100" : "hover:border-slate-300",
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <DocumentsToolbar
          owner={ownerFilter}
          onOwnerChange={handleOwnerChange}
          status={statusFilter}
          onStatusChange={handleStatusChange}
          search={searchTerm}
          onSearchChange={setSearchTerm}
          onUploadClick={handleUploadClick}
          isUploading={uploadDocuments.isPending}
          resultCount={resultCount}
          totalCount={totalCount}
        />

        <div className="relative flex-1">
          {hasVisibleDocuments ? (
            <DocumentsTable
              rows={visibleDocuments}
              sortState={sortState}
              onSortChange={handleSortChange}
              onInspect={handleInspect}
              onDownload={handleDownload}
              onDelete={handleDelete}
              downloadingId={downloadingId}
              deletingId={deletingId}
            />
          ) : (
            <DocumentsEmptyState
              owner={ownerFilter}
              status={statusFilter}
              hasDocuments={hasDocuments}
              onViewAll={() => handleOwnerChange("all")}
              onClearStatus={() => handleStatusChange("all")}
              onUpload={handleUploadClick}
              isUploading={uploadDocuments.isPending}
            />
          )}

          {isDragging ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl border-4 border-dashed border-brand-300 bg-brand-50/80 text-sm font-semibold text-brand-700">
              Drop files to upload
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
