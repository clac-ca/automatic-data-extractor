import clsx from "clsx";
import type { KeyboardEvent } from "react";

import { Button } from "@ui/Button";

import type { DocumentEntry } from "../types";
import { formatRelativeTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { DocumentIcon } from "./icons";
import { MappingBadge } from "./MappingBadge";
import { StatusPill } from "./StatusPill";

export function DocumentsGrid({
  documents,
  activeId,
  selectedIds,
  onSelect,
  onSelectAll,
  onClearSelection,
  allVisibleSelected,
  onActivate,
  onUploadClick,
  onClearFilters,
  showNoDocuments,
  showNoResults,
  isLoading,
  isError,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
  onRefresh,
  now,
  onKeyNavigate,

  selectedCount,
  selectedReadyCount,
  onDownloadSelected,
}: {
  documents: DocumentEntry[];
  activeId: string | null;
  selectedIds: Set<string>;
  onSelect: (id: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  allVisibleSelected: boolean;
  onActivate: (id: string) => void;
  onUploadClick: () => void;
  onClearFilters: () => void;
  showNoDocuments: boolean;
  showNoResults: boolean;
  isLoading: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
  onRefresh: () => void;
  now: number;
  onKeyNavigate: (event: KeyboardEvent<HTMLDivElement>) => void;

  selectedCount: number;
  selectedReadyCount: number;
  onDownloadSelected: () => void;
}) {
  const hasSelectable = documents.some((doc) => doc.record);
  const showLoading = isLoading && documents.length === 0;
  const showError = isError && documents.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      {selectedCount > 0 ? (
        <div className="border-b border-slate-200 bg-slate-50 px-6 py-2">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="font-semibold text-slate-700">
              {selectedCount} selected
              <span className="ml-2 font-normal text-slate-500">
                {selectedReadyCount > 0 ? `${selectedReadyCount} ready to download` : "No ready outputs selected"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                className="text-xs"
                onClick={onDownloadSelected}
                disabled={selectedReadyCount === 0}
              >
                Download selected outputs
              </Button>
              <Button type="button" size="sm" variant="ghost" className="text-xs" onClick={onClearSelection}>
                Clear
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="border-b border-slate-200 bg-white px-6 py-2 text-xs uppercase tracking-[0.18em] text-slate-400">
        <div className="grid grid-cols-[auto_minmax(0,1.8fr)_minmax(0,1.1fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.75fr)] items-center gap-3">
          <div>
            <input
              type="checkbox"
              checked={allVisibleSelected}
              onChange={(event) => (event.target.checked ? onSelectAll() : onClearSelection())}
              aria-label="Select all visible documents"
              disabled={!hasSelectable}
            />
          </div>
          <div>Document</div>
          <div>Status</div>
          <div>Uploader</div>
          <div>Tags</div>
          <div className="text-right">Last activity</div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6" onKeyDown={onKeyNavigate} tabIndex={0} role="list">
        {showLoading ? (
          <div className="py-8">
            <EmptyState title="Loading documents" description="Fetching the latest processing activity." />
          </div>
        ) : showError ? (
          <div className="py-8">
            <EmptyState
              title="Unable to load documents"
              description="We could not refresh this view. Try again."
              action={{ label: "Try again", onClick: onRefresh }}
            />
          </div>
        ) : showNoDocuments ? (
          <div className="py-8">
            <EmptyState
              title="No documents yet"
              description="Upload your first batch to start the processing loop."
              action={{ label: "Upload files", onClick: onUploadClick }}
            />
          </div>
        ) : showNoResults ? (
          <div className="py-8">
            <EmptyState
              title="No results"
              description="Try clearing filters or adjusting the search."
              action={{ label: "Clear filters", onClick: onClearFilters }}
            />
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {documents.map((doc) => {
              const isSelectable = Boolean(doc.record);
              const showStage = Boolean(doc.stage);
              const showProgress = typeof doc.progress === "number" && doc.progress !== null;

              return (
                <div
                  key={doc.id}
                  role="listitem"
                  onClick={() => onActivate(doc.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onActivate(doc.id);
                    }
                  }}
                  className={clsx(
                    "grid cursor-pointer grid-cols-[auto_minmax(0,1.8fr)_minmax(0,1.1fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.75fr)] items-center gap-3 px-2 py-3 transition",
                    activeId === doc.id ? "bg-brand-50" : "hover:bg-slate-50",
                  )}
                  tabIndex={0}
                >
                  <div>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(doc.id)}
                      onChange={() => {
                        if (isSelectable) {
                          onSelect(doc.id);
                        }
                      }}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Select ${doc.name}`}
                      disabled={!isSelectable}
                    />
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
                      <DocumentIcon className="h-4 w-4 text-slate-500" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{doc.name}</p>
                      <p className="text-xs text-slate-500">
                        Uploaded {formatRelativeTime(now, doc.createdAt)} · {doc.size}
                      </p>
                    </div>
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <StatusPill status={doc.status} />
                      {/* MappingBadge intentionally hides "pending" to reduce noise; only shows when actionable. */}
                      <MappingBadge mapping={doc.mapping} />
                    </div>

                    {showStage ? (
                      <div className="mt-1 text-[11px] text-slate-400">
                        <span>{doc.stage}</span>
                        {showProgress && doc.progress !== null ? (
                          <span className="ml-2 text-slate-500">{Math.round(doc.progress)}%</span>
                        ) : null}
                        {showProgress && doc.progress !== null ? (
                          <div className="mt-1 h-1.5 w-full rounded-full bg-slate-200">
                            <div
                              className="h-1.5 rounded-full bg-brand-500"
                              style={{ width: `${Math.max(0, Math.min(100, doc.progress))}%` }}
                            />
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  <div className="text-xs font-semibold text-slate-500">{doc.uploader ?? "Unassigned"}</div>

                  <div className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
                    {doc.tags.length === 0 ? (
                      <span className="text-[11px]">No tags</span>
                    ) : (
                      <>
                        {doc.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold"
                          >
                            {tag}
                          </span>
                        ))}
                        {doc.tags.length > 2 ? (
                          <span className="text-[11px] text-slate-400">+{doc.tags.length - 2}</span>
                        ) : null}
                      </>
                    )}
                  </div>

                  <div className="text-right text-xs text-slate-500">{formatRelativeTime(now, doc.updatedAt)}</div>
                </div>
              );
            })}

            {hasNextPage ? (
              <div className="flex justify-center py-4">
                <button
                  type="button"
                  onClick={onLoadMore}
                  className="text-xs font-semibold text-brand-600"
                  disabled={isFetchingNextPage}
                >
                  {isFetchingNextPage ? "Loading more..." : "Load more"}
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
