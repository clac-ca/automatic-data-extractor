import { type ChangeEvent, type MutableRefObject } from "react";
import clsx from "clsx";

import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

import type { DocumentStatus, ViewMode } from "../types";
import { formatRelativeTime } from "../utils";
import { BoardIcon, DocumentIcon, GridIcon, RefreshIcon, SearchIcon, UploadIcon } from "./icons";

type StatusFilterValue = DocumentStatus | "all";

export function DocumentsHeader({
  search,
  onSearchChange,
  searchRef,
  viewMode,
  onViewModeChange,
  onUploadClick,
  fileInputRef,
  onFileInputChange,

  now,
  lastSyncedAt,
  isRefreshing,
  onRefresh,

  statusFilter,
  statusCounts,
  filteredTotal,
  onStatusFilterChange,

  hasFilters,
  onClearFilters,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchRef: MutableRefObject<HTMLInputElement | null>;
  viewMode: ViewMode;
  onViewModeChange: (value: ViewMode) => void;
  onUploadClick: () => void;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  onFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;

  now: number;
  lastSyncedAt: number | null;
  isRefreshing: boolean;
  onRefresh: () => void;

  statusFilter: StatusFilterValue;
  statusCounts: Record<DocumentStatus, number>;
  filteredTotal: number;
  onStatusFilterChange: (value: StatusFilterValue) => void;

  hasFilters: boolean;
  onClearFilters: () => void;
}) {
  const filters: Array<{ key: StatusFilterValue; label: string; count: number }> = [
    { key: "all", label: "All", count: filteredTotal },
    { key: "ready", label: "Ready", count: statusCounts.ready },
    { key: "failed", label: "Failed", count: statusCounts.failed },
    { key: "processing", label: "Processing", count: statusCounts.processing },
    { key: "queued", label: "Queued", count: statusCounts.queued },
    { key: "archived", label: "Archived", count: statusCounts.archived },
  ];

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-slate-100 text-slate-700">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-900">Documents</h1>
            <p className="text-xs text-slate-500">Clean grid, fast preview</p>
          </div>
        </div>

        <div className="flex min-w-[240px] flex-1 items-center">
          <label className="sr-only" htmlFor="documents-v9-search">
            Search documents
          </label>
          <div className="relative w-full">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <SearchIcon className="h-4 w-4" />
            </span>
            <Input
              id="documents-v9-search"
              ref={searchRef}
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search by name, uploader, or tag ( / )"
              className="pl-9"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs shadow-sm">
            <Button
              type="button"
              size="sm"
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("grid")}
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "grid" ? "shadow-sm" : "text-slate-500")}
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
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "board" ? "shadow-sm" : "text-slate-500")}
              aria-pressed={viewMode === "board"}
              aria-label="Board view"
            >
              <BoardIcon className="h-4 w-4" />
              Board
            </Button>
          </div>

          <Button
            type="button"
            size="md"
            variant="ghost"
            onClick={onRefresh}
            aria-label="Refresh"
            disabled={isRefreshing}
            className="h-10 w-10 p-0"
          >
            <RefreshIcon className={clsx("h-4 w-4", isRefreshing && "animate-spin")} />
          </Button>

          <Button type="button" onClick={onUploadClick} size="md" className="gap-2">
            <UploadIcon className="h-4 w-4" />
            Upload
          </Button>
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onFileInputChange} />
        </div>
      </div>

      <div className="border-t border-slate-100 bg-white px-6 py-2">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-2 font-semibold text-slate-500">
            <span>Status</span>
            <div className="flex flex-wrap items-center rounded-full border border-slate-200 bg-slate-50 p-1">
              {filters.map((filter) => (
                <button
                  key={filter.key}
                  type="button"
                  onClick={() => onStatusFilterChange(filter.key)}
                  className={clsx(
                    "flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold transition",
                    statusFilter === filter.key
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-800",
                  )}
                  aria-pressed={statusFilter === filter.key}
                >
                  {filter.label}
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                    {filter.count}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-slate-500">
            {lastSyncedAt ? <span>Synced {formatRelativeTime(now, lastSyncedAt)}</span> : null}
            {hasFilters ? (
              <Button type="button" size="sm" variant="ghost" onClick={onClearFilters} className="text-xs">
                Clear filters
              </Button>
            ) : (
              <span className="text-slate-400">Tip: ↑/↓ to navigate · Enter to preview</span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
