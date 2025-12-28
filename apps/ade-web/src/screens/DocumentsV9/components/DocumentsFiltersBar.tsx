import clsx from "clsx";
import type { DocumentStatus, DocumentsFilters, FileType, TagMode } from "../types";
import { TagPicker } from "./TagPicker";

const STATUS_LABEL: Record<DocumentStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
  archived: "Archived",
};

const FILETYPE_LABEL: Record<FileType, string> = {
  xlsx: "XLSX",
  xls: "XLS",
  csv: "CSV",
  pdf: "PDF",
  unknown: "Other",
};

export function DocumentsFiltersBar({
  workspaceId,
  filters,
  onToggleStatus,
  onToggleFileType,
  onSetTagMode,
  onToggleTag,
  onClearAll,
  showingCount,
  totalCount,
}: {
  workspaceId: string;
  filters: DocumentsFilters;
  onToggleStatus: (status: DocumentStatus) => void;
  onToggleFileType: (type: FileType) => void;
  onSetTagMode: (mode: TagMode) => void;
  onToggleTag: (tag: string) => void;
  onClearAll: () => void;
  showingCount: number;
  totalCount: number;
}) {
  const hasAnyFilters =
    filters.statuses.length > 0 ||
    filters.fileTypes.length > 0 ||
    filters.tags.length > 0;

  const statusOptions: DocumentStatus[] = ["queued", "processing", "ready", "failed", "archived"];
  const fileTypeOptions: FileType[] = ["xlsx", "xls", "csv", "pdf"];

  return (
    <div className="border-b border-slate-200 bg-white px-6 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Status filter */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-500">Status</span>
            <div className="flex flex-wrap items-center gap-1">
              {statusOptions.map((status) => {
                const active = filters.statuses.includes(status);
                return (
                  <button
                    key={status}
                    type="button"
                    onClick={() => onToggleStatus(status)}
                    className={clsx(
                      "rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                      active
                        ? "border-brand-300 bg-brand-50 text-slate-900"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:text-slate-900",
                    )}
                    aria-pressed={active}
                  >
                    {STATUS_LABEL[status]}
                  </button>
                );
              })}
            </div>
          </div>

          <span className="mx-1 hidden h-6 w-px bg-slate-200 md:block" />

          {/* File type filter */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-500">Type</span>
            <div className="flex flex-wrap items-center gap-1">
              {fileTypeOptions.map((t) => {
                const active = filters.fileTypes.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => onToggleFileType(t)}
                    className={clsx(
                      "rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                      active
                        ? "border-brand-300 bg-brand-50 text-slate-900"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:text-slate-900",
                    )}
                    aria-pressed={active}
                  >
                    {FILETYPE_LABEL[t]}
                  </button>
                );
              })}
            </div>
          </div>

          <span className="mx-1 hidden h-6 w-px bg-slate-200 md:block" />

          {/* Tag filter */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-500">Tags</span>

            <div className="flex items-center rounded-full border border-slate-200 bg-slate-50 p-1 text-xs">
              <button
                type="button"
                onClick={() => onSetTagMode("any")}
                className={clsx(
                  "rounded-full px-3 py-1 font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                  filters.tagMode === "any" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
                )}
                aria-pressed={filters.tagMode === "any"}
              >
                Any
              </button>
              <button
                type="button"
                onClick={() => onSetTagMode("all")}
                className={clsx(
                  "rounded-full px-3 py-1 font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                  filters.tagMode === "all" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
                )}
                aria-pressed={filters.tagMode === "all"}
              >
                All
              </button>
            </div>

            <TagPicker
              workspaceId={workspaceId}
              selected={filters.tags}
              onToggle={onToggleTag}
              placeholder={filters.tags.length ? "Edit tags" : "Filter tags"}
            />
          </div>

          {hasAnyFilters ? (
            <button
              type="button"
              onClick={onClearAll}
              className="ml-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
            >
              Clear all
            </button>
          ) : null}
        </div>

        <div className="text-xs text-slate-500">
          Showing <span className="font-semibold text-slate-900">{showingCount}</span> of{" "}
          <span className="font-semibold text-slate-900">{totalCount}</span>
        </div>
      </div>
    </div>
  );
}
