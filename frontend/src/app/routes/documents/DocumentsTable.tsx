import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";

import type { DocumentRecord } from "../../../shared/types/documents";

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
  readonly downloadingId?: string | null;
}

const uploadedFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function DocumentsTable({
  documents,
  selectedIds,
  onToggleDocument,
  onToggleAll,
  disableSelection = false,
  disableRowActions = false,
  formatStatusLabel,
  onDeleteDocument,
  onDownloadDocument,
  downloadingId = null,
}: DocumentsTableProps) {
  const headerCheckboxRef = useRef<HTMLInputElement | null>(null);

  const { allSelected, someSelected } = useMemo(() => {
    if (documents.length === 0) {
      return { allSelected: false, someSelected: false };
    }
    const selectedCount = documents.reduce(
      (count, document) => (selectedIds.has(document.document_id) ? count + 1 : count),
      0,
    );
    return {
      allSelected: selectedCount === documents.length,
      someSelected: selectedCount > 0 && selectedCount < documents.length,
    };
  }, [documents, selectedIds]);

  useEffect(() => {
    if (headerCheckboxRef.current) {
      headerCheckboxRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full table-auto border-separate border-spacing-0 text-sm text-slate-700">
        <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500 shadow-sm">
          <tr>
            <th scope="col" className="w-10 px-3 py-2">
              <input
                ref={headerCheckboxRef}
                type="checkbox"
                className="h-4 w-4 rounded border border-slate-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                checked={allSelected}
                onChange={onToggleAll}
                disabled={disableSelection || documents.length === 0}
              />
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              Name
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              Status
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              Uploaded
            </th>
            <th scope="col" className="px-3 py-2 text-right">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const isSelected = selectedIds.has(document.document_id);
            return (
              <tr
                key={document.document_id}
                className={clsx(
                  "border-b border-slate-200 last:border-b-0 transition hover:bg-slate-50",
                  isSelected ? "bg-brand-50" : "bg-white",
                )}
              >
                <td className="px-3 py-2 align-middle">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border border-slate-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    checked={isSelected}
                    onChange={() => onToggleDocument(document.document_id)}
                    disabled={disableSelection}
                  />
                </td>
                <td className="px-3 py-2 align-middle">
                  <div className="flex flex-col gap-1">
                    <span className="truncate font-semibold text-slate-900" title={document.name}>
                      {document.name}
                    </span>
                    <span className="flex items-center gap-2 text-xs text-slate-500">
                      {formatFileDescription(document)}
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2 align-middle">
                  <span className={clsx("rounded-full px-2 py-1 text-[11px] font-semibold uppercase", statusBadgeClass(document.status))}>
                    {formatStatusLabel ? formatStatusLabel(document.status) : document.status}
                  </span>
                </td>
                <td className="px-3 py-2 align-middle">
                  <time
                    dateTime={document.created_at}
                    className="block truncate text-xs text-slate-600"
                    title={uploadedFormatter.format(new Date(document.created_at))}
                  >
                    {formatUploadedAt(document)}
                  </time>
                </td>
                <td className="px-3 py-2 align-middle text-right">
                  <DocumentActionsMenu
                    document={document}
                    onDownload={onDownloadDocument}
                    onDelete={onDeleteDocument}
                    disabled={disableRowActions}
                    downloading={downloadingId === document.document_id}
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

function formatFileDescription(document: DocumentRecord) {
  const parts: string[] = [];
  if (document.content_type) {
    parts.push(humanizeContentType(document.content_type));
  }
  if (typeof document.byte_size === "number" && document.byte_size >= 0) {
    parts.push(formatFileSize(document.byte_size));
  }
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
  if (bytes < 1024) {
    return `${bytes} B`;
  }
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
  const date = new Date(document.created_at);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return uploadedFormatter.format(date);
}

interface DocumentActionsMenuProps {
  readonly document: DocumentRecord;
  readonly onDownload?: (document: DocumentRecord) => void;
  readonly onDelete?: (document: DocumentRecord) => void;
  readonly disabled?: boolean;
  readonly downloading?: boolean;
}

export function DocumentActionsMenu({
  document,
  onDownload,
  onDelete,
  disabled = false,
  downloading = false,
}: DocumentActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handlePointerDown(event: PointerEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("pointerdown", handlePointerDown, { capture: true });
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown, { capture: true });
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const toggle = () => {
    if (disabled) {
      return;
    }
    setOpen((value) => !value);
  };

  const handleDownload = () => {
    setOpen(false);
    onDownload?.(document);
  };

  const handleDelete = () => {
    setOpen(false);
    onDelete?.(document);
  };

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:cursor-not-allowed"
        onClick={toggle}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
      >
        <span className="sr-only">Document actions</span>
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          className={clsx("h-4 w-4", downloading ? "animate-pulse text-brand-600" : "text-current")}
        >
          <circle cx="4" cy="10" r="1.8" />
          <circle cx="10" cy="10" r="1.8" />
          <circle cx="16" cy="10" r="1.8" />
        </svg>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-9 z-20 w-40 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-center justify-between px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-100"
            onClick={handleDownload}
            disabled={!onDownload}
          >
            <span>Download</span>
          </button>
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-center justify-between px-3 py-2 text-sm text-slate-400 transition hover:bg-slate-100"
            disabled
            title="Coming soon"
          >
            <span>Reprocess</span>
            <span className="text-[10px] uppercase tracking-wide">Soon</span>
          </button>
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-center justify-between px-3 py-2 text-sm font-semibold text-danger-600 transition hover:bg-danger-50 hover:text-danger-700"
            onClick={handleDelete}
            disabled={!onDelete}
          >
            <span>Delete</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
