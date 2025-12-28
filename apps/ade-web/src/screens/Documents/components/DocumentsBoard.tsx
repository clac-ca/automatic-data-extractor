import clsx from "clsx";

import type { BoardColumn, BoardGroup, WorkspacePerson } from "../types";
import { formatRelativeTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { MappingBadge } from "./MappingBadge";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "./PeoplePicker";

const STATUS_DOT: Record<string, string> = {
  queued: "bg-muted-foreground",
  processing: "bg-warning-500",
  ready: "bg-success-500",
  failed: "bg-danger-500",
  archived: "bg-muted",
};

export function DocumentsBoard({
  columns,
  groupBy,
  onGroupByChange,
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

  people,
  onAssign,
  onPickUp,
}: {
  columns: BoardColumn[];
  groupBy: BoardGroup;
  onGroupByChange: (value: BoardGroup) => void;
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

  people: WorkspacePerson[];
  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onPickUp: (documentId: string) => void;
}) {
  const totalItems = columns.reduce((sum, column) => sum + column.items.length, 0);
  const showLoading = isLoading && totalItems === 0;
  const showError = isError && totalItems === 0;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-6 py-3 text-xs">
        <div className="flex items-center gap-2 font-semibold text-muted-foreground">
          <span>Group by</span>
          <div className="flex items-center rounded-full border border-border bg-background px-1 py-1">
            {(["status", "tag", "uploader"] as const).map((group) => (
              <button
                key={group}
                type="button"
                onClick={() => onGroupByChange(group)}
                className={clsx(
                  "rounded-full px-3 py-1 text-xs font-semibold transition",
                  groupBy === group ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={groupBy === group}
              >
                {group === "status" ? "Status" : group === "tag" ? "Tag" : "Uploader"}
              </button>
            ))}
          </div>
        </div>
        <span className="text-muted-foreground">Select a card to open the preview.</span>
      </div>

      <div className="flex-1 min-h-0 overflow-auto px-6 py-4">
        {showLoading ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-border bg-card text-sm text-muted-foreground">
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
            {columns.map((column) => (
              <div key={column.id} className="flex w-72 min-w-[18rem] flex-col">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{column.label}</p>
                    <p className="text-xs text-muted-foreground">{column.items.length} items</p>
                  </div>
                </div>

                <div className="flex min-h-[12rem] flex-1 flex-col gap-3 rounded-2xl border border-dashed border-border bg-card px-3 py-3">
                  {column.items.length === 0 ? (
                    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-xs text-muted-foreground">
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
                          "flex cursor-pointer flex-col gap-3 rounded-2xl border bg-card px-3 py-3 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                          activeId === doc.id ? "border-brand-400" : "border-border hover:border-brand-300",
                        )}
                        role="button"
                        tabIndex={0}
                        aria-label={`Open ${doc.name}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-foreground">{doc.name}</p>
                            <p className="text-xs text-muted-foreground">Updated {formatRelativeTime(now, doc.updatedAt)}</p>
                          </div>
                          <span className={clsx("h-2.5 w-2.5 rounded-full", STATUS_DOT[doc.status])} aria-hidden />
                        </div>

                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                          <span className="font-semibold">Assignee: {doc.assigneeLabel ?? "Unassigned"}</span>
                          {!doc.assigneeKey ? (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onPickUp(doc.id);
                              }}
                              className="shrink-0 whitespace-nowrap rounded-full border border-brand-200 bg-brand-50 px-2 py-0.5 font-semibold text-brand-700"
                            >
                              Pick up
                            </button>
                          ) : null}
                          <div
                            onClick={(event) => event.stopPropagation()}
                            className="min-w-0 rounded-full border border-border bg-background px-1 py-0.5"
                          >
                            <PeoplePicker
                              people={people}
                              value={[doc.assigneeKey ?? unassignedKey()]}
                              onChange={(keys) => onAssign(doc.id, normalizeSingleAssignee(keys))}
                              placeholder="Assign..."
                              includeUnassigned
                              buttonClassName="min-w-0 max-w-[11rem] border-0 bg-transparent px-2 py-0 text-[11px] shadow-none"
                            />
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                          <span className="font-semibold">{doc.uploader ?? "Unassigned"}</span>
                          {doc.tags.length > 0 ? (
                            <span className="rounded-full border border-border bg-background px-2 py-0.5">
                              {doc.tags[0]}
                              {doc.tags.length > 1 ? ` +${doc.tags.length - 1}` : ""}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">No tags</span>
                          )}
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
        <div className="flex shrink-0 justify-center border-t border-border bg-card px-6 py-3">
          <button type="button" onClick={onLoadMore} className="text-xs font-semibold text-brand-600" disabled={isFetchingNextPage}>
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
