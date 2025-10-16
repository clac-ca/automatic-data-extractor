import clsx from "clsx";

import { Button } from "../../../../ui";
import type { DocumentRow, SortColumn, SortState } from "../utils";
import { formatDateTime, formatFileSize, formatRelativeTime, formatStatusLabel } from "../utils";

interface DocumentsTableProps {
  readonly rows: readonly DocumentRow[];
  readonly sortState: SortState;
  readonly onSortChange: (column: SortColumn) => void;
  readonly onInspect: (row: DocumentRow) => void;
  readonly onDownload: (row: DocumentRow) => void;
  readonly onDelete: (row: DocumentRow) => void;
  readonly downloadingId: string | null;
  readonly deletingId: string | null;
}

const columns: { id: SortColumn | "tags" | "actions"; label: string; widthClass?: string; align?: "start" | "center" | "end"; sortable?: boolean }[] = [
  { id: "name", label: "Document", widthClass: "w-[26%]", sortable: true },
  { id: "status", label: "Status", widthClass: "w-[11%]", sortable: true },
  { id: "source", label: "Source", widthClass: "w-[13%]", sortable: true },
  { id: "uploadedAt", label: "Uploaded", widthClass: "w-[14%]", sortable: true },
  { id: "lastRunAt", label: "Last run", widthClass: "w-[14%]", sortable: true },
  { id: "byteSize", label: "Size", widthClass: "w-[8%]", sortable: true, align: "end" },
  { id: "tags", label: "Tags", widthClass: "w-[14%]" },
  { id: "actions", label: "Actions", widthClass: "w-[10%]", align: "end" },
];

const STATUS_BADGES = {
  inbox: "bg-indigo-100 text-indigo-700",
  processing: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-danger-100 text-danger-700",
  archived: "bg-slate-200 text-slate-700",
} as const satisfies Record<DocumentRow["status"], string>;

export function DocumentsTable({
  rows,
  sortState,
  onSortChange,
  onInspect,
  onDownload,
  onDelete,
  downloadingId,
  deletingId,
}: DocumentsTableProps) {
  return (
    <div role="grid" className="absolute inset-0 overflow-auto">
      <table className="min-w-full border-separate border-spacing-0 text-sm">
        <caption className="sr-only">Workspace documents</caption>
        <colgroup>
          {columns.map((column) => (
            <col key={column.id} className={column.widthClass} />
          ))}
        </colgroup>
        <thead className="sticky top-0 z-10 bg-white shadow-[0_1px_0_rgba(15,23,42,0.08)]">
          <tr>
            {columns.map((column) => (
              <TableHeaderCell
                key={column.id}
                column={column}
                sortState={sortState}
                onSortChange={onSortChange}
              />
            ))}
          </tr>
        </thead>
        <tbody className="bg-white">
          {rows.map((row) => (
            <DocumentsRow
              key={row.id}
              row={row}
              onInspect={onInspect}
              onDownload={onDownload}
              onDelete={onDelete}
              isDownloading={downloadingId === row.id}
              isDeleting={deletingId === row.id}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface HeaderColumn {
  readonly id: (typeof columns)[number]["id"];
  readonly label: string;
  readonly widthClass?: string;
  readonly align?: "start" | "center" | "end";
  readonly sortable?: boolean;
}

interface TableHeaderCellProps {
  readonly column: HeaderColumn;
  readonly sortState: SortState;
  readonly onSortChange: (column: SortColumn) => void;
}

function TableHeaderCell({ column, sortState, onSortChange }: TableHeaderCellProps) {
  const alignment =
    column.align === "end"
      ? "justify-end text-right"
      : column.align === "center"
        ? "justify-center text-center"
        : "justify-start text-left";

  const baseClass = "px-4 py-3 text-xs font-semibold uppercase tracking-wide";

  if (!column.sortable) {
    return (
      <th scope="col" className={clsx(baseClass, "text-slate-500", alignment)}>
        {column.label}
      </th>
    );
  }

  const isActive = sortState.column === column.id;
  const nextDirection = isActive && sortState.direction === "asc" ? "desc" : "asc";
  const ariaSort = isActive ? (sortState.direction === "asc" ? "ascending" : "descending") : "none";

  return (
    <th scope="col" className="px-4 py-3" aria-sort={ariaSort}>
      <button
        type="button"
        onClick={() => onSortChange(column.id as SortColumn)}
        className={clsx(
          "flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wide transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
          alignment,
          isActive ? "text-brand-600" : "text-slate-500 hover:text-slate-700",
        )}
      >
        <span className="truncate">{column.label}</span>
        <span aria-hidden="true" className={clsx("text-[10px]", isActive ? "opacity-100" : "opacity-0")}> 
          {isActive ? (sortState.direction === "asc" ? "▲" : "▼") : "▲"}
        </span>
        <span className="sr-only">Sort by {column.label} ({nextDirection})</span>
      </button>
    </th>
  );
}

interface DocumentsRowProps {
  readonly row: DocumentRow;
  readonly onInspect: (row: DocumentRow) => void;
  readonly onDownload: (row: DocumentRow) => void;
  readonly onDelete: (row: DocumentRow) => void;
  readonly isDownloading: boolean;
  readonly isDeleting: boolean;
}

function DocumentsRow({ row, onInspect, onDownload, onDelete, isDownloading, isDeleting }: DocumentsRowProps) {
  const isBusy = isDownloading || isDeleting;

  return (
    <tr
      className={clsx("border-b border-slate-100 last:border-b-0", isBusy ? "opacity-60" : "", "hover:bg-slate-50")}
      aria-busy={isBusy || undefined}
    >
      <th scope="row" className="px-4 py-4 align-top">
        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={() => onInspect(row)}
            className="max-w-full truncate text-left text-sm font-semibold text-slate-900 transition hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
          >
            {row.name}
          </button>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>{row.uploaderName}</span>
            {row.contentType ? <span className="text-slate-400">• {row.contentType}</span> : null}
          </div>
        </div>
      </th>
      <td className="px-4 py-4 align-top">
        <StatusBadge status={row.status} />
      </td>
      <td className="px-4 py-4 align-top text-slate-700">
        <span className="block truncate" title={row.source}>
          {row.source}
        </span>
      </td>
      <td className="px-4 py-4 align-top text-slate-700">
        <Timestamp value={row.uploadedAt} />
      </td>
      <td className="px-4 py-4 align-top text-slate-700">
        {row.lastRunAt ? <Timestamp value={row.lastRunAt} description={row.lastRunLabel} /> : <span className="text-sm text-slate-500">{row.lastRunLabel}</span>}
      </td>
      <td className="px-4 py-4 align-top text-right text-sm font-semibold text-slate-700">{formatFileSize(row.byteSize)}</td>
      <td className="px-4 py-4 align-top">
        <TagList tags={row.tags} />
      </td>
      <td className="px-4 py-4 align-top">
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => onInspect(row)}>
            Details
          </Button>
          <Button variant="secondary" size="sm" onClick={() => onDownload(row)} isLoading={isDownloading}>
            Download
          </Button>
          <Button variant="danger" size="sm" onClick={() => onDelete(row)} isLoading={isDeleting}>
            Delete
          </Button>
        </div>
      </td>
    </tr>
  );
}

function Timestamp({ value, description }: { readonly value: Date; readonly description?: string }) {
  return (
    <div className="flex flex-col">
      <time dateTime={value.toISOString()}>{formatDateTime(value)}</time>
      <span className="text-xs text-slate-400">
        {description ? `${description} • ` : ""}
        {formatRelativeTime(value)}
      </span>
    </div>
  );
}

function TagList({ tags }: { readonly tags: readonly string[] }) {
  if (!tags.length) {
    return <span className="text-slate-400">—</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">
          {tag}
        </span>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { readonly status: DocumentRow["status"] }) {
  return (
    <span
      className={clsx("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold", STATUS_BADGES[status])}
      aria-label={`Status: ${formatStatusLabel(status)}`}
    >
      {formatStatusLabel(status)}
    </span>
  );
}
