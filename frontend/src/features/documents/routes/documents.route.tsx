import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

import { useWorkspaceContext } from "../../workspaces/context/WorkspaceContext";
import { useWorkspacePageHeaderController } from "../../../app/workspaces/WorkspacePageHeaderContext";
import { useWorkspaceDocumentsQuery, type DocumentsStatusFilter } from "../api/queries";
import { DocumentsTable } from "../components/DocumentsTable";
import { useDeleteDocuments } from "../hooks/useDeleteDocuments";
import { useUploadDocuments } from "../hooks/useUploadDocuments";
import { downloadWorkspaceDocument } from "../api";
import type { DocumentStatus } from "../../../shared/types/documents";
import { Button } from "../../../ui/button";
import { Input } from "../../../ui/input";
import { Select } from "../../../ui/select";

const STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

type StatusFilter = "all" | DocumentStatus;

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const { setHeader } = useWorkspacePageHeaderController();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortOrder, setSortOrder] = useState("-created_at");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const documentsQuery = useWorkspaceDocumentsQuery(
    workspace.id,
    useMemo(() => {
      const status: DocumentsStatusFilter | undefined = statusFilter === "all" ? undefined : statusFilter;
      const search = searchTerm.trim() || undefined;
      const sort = sortOrder;
      return { status, search, sort };
    }, [statusFilter, searchTerm, sortOrder]),
  );
  const uploadDocuments = useUploadDocuments(workspace.id);
  const deleteDocuments = useDeleteDocuments(workspace.id);

  const documents = documentsQuery.data?.items ?? [];
  const selectedCount = selectedIds.size;

  const handleUploadFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) {
        return;
      }
      uploadDocuments.mutate({ files });
    },
    [uploadDocuments],
  );

  useEffect(() => {
    const primaryAction = (
      <Button onClick={() => fileInputRef.current?.click()} isLoading={uploadDocuments.isPending}>
        Upload documents
      </Button>
    );
    const cleanup = setHeader({
      title: "Documents",
      description: `Track uploads in ${workspace.name ?? "this workspace"}.`,
      primaryAction,
    });
    return cleanup;
  }, [setHeader, uploadDocuments.isPending, workspace.name]);

  const statusFormatter = (status: DocumentStatus) => STATUS_LABELS[status] ?? status;

  return (
    <div className="space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
        multiple
        className="hidden"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length > 0) {
            handleUploadFiles(files);
          }
          event.target.value = "";
        }}
      />

      <UploadPad
        onChooseFiles={() => fileInputRef.current?.click()}
        onDropFiles={handleUploadFiles}
        isBusy={uploadDocuments.isPending}
      />

      <DocumentsToolbar
        search={searchTerm}
        onSearch={setSearchTerm}
        status={statusFilter}
        onStatus={setStatusFilter}
        sort={sortOrder}
        onSort={setSortOrder}
        onReset={() => {
          setSearchTerm("");
          setStatusFilter("all");
          setSortOrder("-created_at");
        }}
      />

      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700">
        {documentsQuery.isLoading ? (
          <p>Loading documents…</p>
        ) : documentsQuery.isError ? (
          <p className="text-rose-600">We could not load documents.</p>
        ) : documents.length === 0 ? (
          <p>No documents yet. Use the upload pad above to add files.</p>
        ) : (
          <DocumentsTable
            documents={documents}
            selectedIds={selectedIds}
            onToggleDocument={(id) => {
              setSelectedIds((current) => {
                const next = new Set(current);
                next.has(id) ? next.delete(id) : next.add(id);
                return next;
              });
            }}
            onToggleAll={() => {
              setSelectedIds((current) => {
                if (documents.length === 0) return new Set();
                if (current.size === documents.length) return new Set();
                return new Set(documents.map((doc) => doc.document_id));
              });
            }}
            disableSelection={uploadDocuments.isPending || deleteDocuments.isPending}
            disableRowActions={deleteDocuments.isPending}
            formatStatusLabel={statusFormatter}
            onDeleteDocument={(doc) => deleteDocuments.mutate({ documentIds: [doc.document_id] })}
            onDownloadDocument={async (doc) => {
              const { blob, filename } = await downloadWorkspaceDocument(workspace.id, doc.document_id);
              triggerDownload(blob, filename ?? doc.name);
            }}
            onRunDocument={() => undefined}
            downloadingId={null}
            renderJobStatus={() => null}
          />
        )}
      </div>

      {selectedCount > 0 ? (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 px-4 py-2 shadow">
          <span className="text-sm font-medium text-slate-700">{selectedCount} selected</span>
          <Button
            size="sm"
            variant="danger"
            disabled={deleteDocuments.isPending}
            onClick={() => deleteDocuments.mutate({ documentIds: Array.from(selectedIds) })}
          >
            Delete selected
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
            Clear
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function UploadPad({
  onChooseFiles,
  onDropFiles,
  isBusy,
}: {
  onChooseFiles: () => void;
  onDropFiles: (files: File[]) => void;
  isBusy: boolean;
}) {
  const [isDragActive, setDragActive] = useState(false);

  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-8 py-12 text-center transition",
        isDragActive ? "border-brand-400 bg-brand-50 shadow" : "border-slate-300 bg-slate-100",
      )}
      onDragEnter={(event) => {
        if (!event.dataTransfer?.types.includes("Files")) return;
        event.preventDefault();
        setDragActive(true);
      }}
      onDragOver={(event) => {
        if (!event.dataTransfer?.types.includes("Files")) return;
        event.preventDefault();
      }}
      onDragLeave={(event) => {
        if (event.currentTarget.contains(event.relatedTarget as Node)) {
          return;
        }
        setDragActive(false);
      }}
      onDrop={(event) => {
        const files = Array.from(event.dataTransfer?.files ?? []);
        if (files.length === 0) return;
        event.preventDefault();
        setDragActive(false);
        onDropFiles(files);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onChooseFiles();
        }
      }}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white shadow-sm">
        <svg className="h-6 w-6 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-base font-semibold text-slate-800">Upload documents</p>
      <p className="text-xs text-slate-500">PDF, CSV, TSV, XLS, XLSX, XLSM, XLSB up to 25&nbsp;MB each.</p>
      <Button variant="primary" size="sm" isLoading={isBusy} onClick={onChooseFiles}>
        Choose files
      </Button>
    </div>
  );
}

function DocumentsToolbar({
  search,
  onSearch,
  status,
  onStatus,
  sort,
  onSort,
  onReset,
}: {
  search: string;
  onSearch: (value: string) => void;
  status: StatusFilter;
  onStatus: (value: StatusFilter) => void;
  sort: string;
  onSort: (value: string) => void;
  onReset: () => void;
}) {
  const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
    { value: "all", label: "All" },
    { value: "processing", label: "Processing" },
    { value: "failed", label: "Failed" },
    { value: "uploaded", label: "Uploaded" },
    { value: "processed", label: "Processed" },
    { value: "archived", label: "Archived" },
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          placeholder="Search documents"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          className="min-w-[220px] flex-1"
        />

        <div className="flex flex-wrap items-center gap-1">
          {STATUS_FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={clsx(
                "rounded-full px-2.5 py-1 text-xs font-medium transition",
                status === item.value
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200",
              )}
              onClick={() => onStatus(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <Select value={sort} onChange={(event) => onSort(event.target.value)} className="w-[170px]">
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="name">Name A–Z</option>
          <option value="-name">Name Z–A</option>
          <option value="status">Status</option>
        </Select>

        <Button variant="ghost" size="sm" onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
