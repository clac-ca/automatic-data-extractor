import clsx from "clsx";

import type { BoardColumn, BoardGroup } from "../types";
import { formatRelativeTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { MappingBadge } from "./MappingBadge";
import { StatusPill } from "./StatusPill";

const STATUS_DOT: Record<string, string> = {
  queued: "bg-slate-400",
  processing: "bg-amber-500",
  ready: "bg-emerald-500",
  failed: "bg-rose-500",
  archived: "bg-slate-300",
};

export function DocumentsBoard({
  columns,
  groupBy,
  onGroupByChange,

  hideEmptyColumns,
  onHideEmptyColumnsChange,

  activeId,
  onActivate,
  now,
  isLoading,
  isError,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
  onRefresh,

  onUploadClick,
  onClearFilters,
  showNoDocuments,
  showNoResults,
}: {
  columns: BoardColumn[];
  groupBy: BoardGroup;
  onGroupByChange: (value: BoardGroup) => void;

  hideEmptyColumns: boolean;
  onHideEmptyColumnsChange: (value: boolean) => void;

  activeId: string | null;
  onActivate: (id: string) => void;
  now: number;
  isLoading: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
  onRefresh: () => void;

  onUploadClick: () => void;
  onClearFilters: () => void;
  showNoDocuments: boolean;
  showNoResults: boolean;
}) {
  const totalItems = columns.reduce((sum, column) => sum + column.items.length, 0);
  const showLoading = isLoading && totalItems === 0;
  const showError = isError && totalItems === 0;

  const hiddenCount = hideEmptyColumns ? columns.filter((column) => column.items.length === 0).length : 0;
  const visibleColumns = hideEmptyColumns ? columns.filter((column) => column.items.length > 0) : columns;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-slate-50">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 font-semibold text-slate-500">
            <span>Group by</span>
            <div className="flex items-center rounded-full border border-slate-200 bg-slate-50 px-1 py-1">
              {(["status", "tag", "uploader"] as const).map((group) => (
                <button
                  key={group}
                  type="button"
                  onClick={() => onGroupByChange(group)}
                  className={clsx(
                    "rounded-full px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                    groupBy === group ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
                  )}
                  aria-pressed={groupBy === group}
                >
                  {group === "status" ? "Status" : group === "tag" ? "Tag" : "Uploader"}
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={() => onHideEmptyColumnsChange(!hideEmptyColumns)}
            className={clsx(
              "rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
              hideEmptyColumns
                ? "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                : "border-slate-200 bg-white text-slate-500 hover:text-slate-800",
            )}
            aria-pressed={hideEmptyColumns}
            title={hideEmptyColumns ? "Showing non-empty columns" : "Showing all columns"}
          >
            {hideEmptyColumns ? "Hiding empty" : "Showing empty"}
            {hiddenCount > 0 ? <span className="ml-2 text-slate-400">({hiddenCount})</span> : null}
          </button>
        </div>

        <span className="text-slate-500">Select a card to preview output.</span>
      </div>

      <div className="flex-1 overflow-x-auto px-6 py-4">
        {showLoading ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white text-sm text-slate-500">
            Loading board...
          </div>
        ) : showError ? (
          <EmptyState
            title="Unable to load documents"
            description="We could not refresh this board. Try again."
            action={{ label: "Try again", onClick: onRefresh }}
          />
        ) : showNoDocuments ? (
          <EmptyState
            title="No documents yet"
            description="Upload your first batch to start the processing loop."
            action={{ label: "Upload files", onClick: onUploadClick }}
          />
        ) : showNoResults ? (
          <EmptyState
            title="No results"
            description="Try clearing filters or adjusting the search."
            action={{ label: "Clear filters", onClick: onClearFilters }}
          />
        ) : (
          <div className="flex min-h-full gap-4">
            {visibleColumns.map((column) => (
              <div key={column.id} className="flex w-72 min-w-[18rem] flex-col">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{column.label}</p>
                    <p className="text-xs text-slate-500">{column.items.length} items</p>
                  </div>
                </div>

                <div className="flex min-h-[12rem] flex-1 flex-col gap-3 rounded-2xl border border-dashed border-slate-200 bg-white px-3 py-3">
                  {column.items.length === 0 ? (
                    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-xs text-slate-400">
                      <p>No items yet</p>
                    </div>
                  ) : (
                    column.items.map((doc) => (
                      <div
                        key={doc.id}
                        onClick={() => onActivate(doc.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onActivate(doc.id);
                          }
                        }}
                        className={clsx(
                          "flex cursor-pointer flex-col gap-3 rounded-2xl border bg-white px-3 py-3 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                          activeId === doc.id ? "border-brand-400" : "border-slate-200 hover:border-brand-300",
                        )}
                        role="button"
                        tabIndex={0}
                        aria-label={`Open ${doc.name}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900">{doc.name}</p>
                            <p className="text-xs text-slate-500">Updated {formatRelativeTime(now, doc.updatedAt)}</p>
                          </div>
                          <span className={clsx("h-2.5 w-2.5 rounded-full", STATUS_DOT[doc.status])} aria-hidden />
                        </div>

                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          {/* When not grouped by status, show explicit status for clarity */}
                          {groupBy !== "status" ? <StatusPill status={doc.status} /> : null}

                          {groupBy !== "uploader" ? (
                            <span className="font-semibold">{doc.uploader ?? "Unassigned"}</span>
                          ) : null}

                          {groupBy !== "tag" && doc.tags.length > 0 ? (
                            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">
                              {doc.tags[0]}
                              {doc.tags.length > 1 ? ` +${doc.tags.length - 1}` : ""}
                            </span>
                          ) : null}

                          {/* MappingBadge hides pending by default; shows only if actionable */}
                          <MappingBadge mapping={doc.mapping} />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {hasNextPage ? (
        <div className="flex justify-center border-t border-slate-200 bg-white px-6 py-3">
          <button
            type="button"
            onClick={onLoadMore}
            className="rounded-md text-xs font-semibold text-brand-600 transition hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:text-slate-400"
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
