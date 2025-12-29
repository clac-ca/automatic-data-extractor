import clsx from "clsx";
import { useEffect, useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import type { DocumentEntry, WorkspacePerson } from "../types";
import { getDocumentOutputRun } from "../data";
import { fileTypeLabel, formatRelativeTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { ChatIcon, DocumentIcon, DownloadIcon, UserIcon } from "./icons";
import { MappingBadge } from "./MappingBadge";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "./PeoplePicker";
import { RowActionsMenu } from "./RowActionsMenu";
import { StatusPill } from "./StatusPill";

const INTERACTIVE_SELECTOR =
  "button, a, input, select, textarea, [role='button'], [role='menuitem'], [data-ignore-row-click='true']";

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest(INTERACTIVE_SELECTOR));
}

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

  people,
  onAssign,
  onPickUp,

  onDownloadOriginal,
  onDownloadOutput,
  onCopyLink,
  onReprocess,
  onOpenDetails,
  onOpenNotes,
  onClosePreview,
  expandedId,
  expandedContent,
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

  people: WorkspacePerson[];
  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onPickUp: (documentId: string) => void;

  onDownloadOriginal: (doc: DocumentEntry | null) => void;
  onDownloadOutput: (doc: DocumentEntry) => void;
  onCopyLink: (doc: DocumentEntry | null) => void;
  onReprocess: (doc: DocumentEntry) => void;
  onOpenDetails: (docId: string) => void;
  onOpenNotes: (docId: string) => void;
  onClosePreview: () => void;
  expandedId?: string | null;
  expandedContent?: ReactNode;
}) {
  const hasSelectable = documents.some((doc) => doc.record);
  const showLoading = isLoading && documents.length === 0;
  const showError = isError && documents.length === 0;
  const listRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    if (!activeId) return;
    const container = listRef.current;
    const row = rowRefs.current.get(activeId);
    if (!container || !row) return;
    const nextTop = row.offsetTop - container.offsetTop;
    container.scrollTo({ top: Math.max(0, nextTop) });
  }, [activeId]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-card">
      <div className="shrink-0 border-b border-border bg-background/40 px-6 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        <div className="grid grid-cols-[auto_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.6fr)_auto] items-center gap-3">
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
          <div>Assignee</div>
          <div>Tags</div>
          <div className="text-right">Updated</div>
          <div className="text-right">Actions</div>
        </div>
      </div>

      <div
        ref={listRef}
        className="flex-1 min-h-0 overflow-y-auto px-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        onKeyDown={onKeyNavigate}
        tabIndex={0}
        role="listbox"
        aria-label="Documents"
      >
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
              description="Upload your first batch to start processing."
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
          <div className="flex flex-col">
            {documents.map((doc) => {
              const isSelectable = Boolean(doc.record);
              const outputRun = getDocumentOutputRun(doc.record);
              const canDownloadOutput = Boolean(outputRun?.run_id);
              const isUnassigned = !doc.assigneeKey;
              const isExpanded = Boolean(expandedContent && expandedId === doc.id);
              const isActive = Boolean(isExpanded && activeId === doc.id);
              const previewId = `documents-preview-${doc.id}`;
              const hasNotes = doc.commentCount > 0;
              const downloadLabel = canDownloadOutput ? "Download output" : "Output not ready";

              return (
                <div
                  key={doc.id}
                  ref={(node) => {
                    if (node) rowRefs.current.set(doc.id, node);
                    else rowRefs.current.delete(doc.id);
                  }}
                  className="border-b border-border/70"
                >
                  <div
                    role="button"
                    onClick={(event) => {
                      if (isInteractiveTarget(event.target)) return;
                      onActivate(doc.id);
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      if (event.currentTarget !== event.target) return;
                      event.preventDefault();
                      onActivate(doc.id);
                    }}
                    className={clsx(
                      "group grid cursor-pointer grid-cols-[auto_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.6fr)_auto] items-center gap-3 py-3 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      isActive ? "bg-brand-50 dark:bg-brand-500/20" : "hover:bg-background dark:hover:bg-muted/40",
                    )}
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    aria-controls={isExpanded ? previewId : undefined}
                  >
                    <div>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(doc.id)}
                        onChange={() => {
                          if (isSelectable) onSelect(doc.id);
                        }}
                        onClick={(event) => event.stopPropagation()}
                        aria-label={`Select ${doc.name}`}
                        disabled={!isSelectable}
                      />
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-background">
                        <DocumentIcon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">{doc.name}</p>
                        <p className="flex items-center gap-2 text-[11px] text-muted-foreground">
                          <span className="text-[10px] font-semibold text-muted-foreground">
                            {fileTypeLabel(doc.fileType)}
                          </span>
                          <span aria-hidden className="text-muted-foreground">·</span>
                          <span>Uploaded {formatRelativeTime(now, doc.createdAt)}</span>
                          <span aria-hidden className="text-muted-foreground">·</span>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              onOpenNotes(doc.id);
                            }}
                            className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-semibold text-muted-foreground transition hover:text-foreground"
                            title={hasNotes ? `${doc.commentCount} notes` : "No notes yet"}
                          >
                            <ChatIcon className="h-3 w-3" />
                            <span className="tabular-nums">{doc.commentCount}</span>
                          </button>
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <StatusPill status={doc.status} />
                      <MappingBadge mapping={doc.mapping} />
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border bg-background">
                        <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                      </span>

                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-foreground">
                          {doc.assigneeLabel ?? "Unassigned"}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          {isUnassigned ? (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onPickUp(doc.id);
                              }}
                              className="shrink-0 whitespace-nowrap text-[11px] font-semibold text-brand-600 hover:text-brand-700"
                            >
                              Pick up
                            </button>
                          ) : null}
                          <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                            <span className="font-semibold">Assign</span>
                            <div data-ignore-row-click className="min-w-0">
                              <PeoplePicker
                                people={people}
                                value={[doc.assigneeKey ?? unassignedKey()]}
                                onChange={(keys) => onAssign(doc.id, normalizeSingleAssignee(keys))}
                                placeholder="Assignee..."
                                includeUnassigned
                                buttonClassName="min-w-0 max-w-[11rem] px-2 py-1 text-[11px]"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="text-xs text-muted-foreground">
                      {doc.tags.length > 0 ? (
                        <span className="rounded-full border border-border bg-background px-2 py-0.5">
                          {doc.tags[0]}
                          {doc.tags.length > 1 ? ` +${doc.tags.length - 1}` : ""}
                        </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                    </div>

                    <div className="text-right text-xs text-muted-foreground">{formatRelativeTime(now, doc.updatedAt)}</div>

                    <div className="flex justify-end" data-ignore-row-click>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            if (canDownloadOutput) onDownloadOutput(doc);
                          }}
                          disabled={!canDownloadOutput}
                          aria-label={downloadLabel}
                          title={downloadLabel}
                          className={clsx(
                            "inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition",
                            "hover:bg-background hover:text-muted-foreground",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                            "disabled:cursor-not-allowed disabled:text-muted-foreground disabled:hover:bg-card disabled:hover:text-muted-foreground",
                          )}
                        >
                          <DownloadIcon className="h-4 w-4" />
                        </button>

                        <RowActionsMenu
                          onOpenDetails={() => onOpenDetails(doc.id)}
                          onReprocess={isExpanded ? () => onReprocess(doc) : undefined}
                          reprocessDisabled={!doc.record || !isExpanded}
                          showClosePreview={isExpanded}
                          onClosePreview={onClosePreview}
                          onDownloadOriginal={() => onDownloadOriginal(doc)}
                          onCopyLink={() => onCopyLink(doc)}
                          originalDisabled={!doc.record}
                          copyDisabled={!doc.record}
                        />
                      </div>
                    </div>
                  </div>

                  {isExpanded ? (
                    <div
                      id={previewId}
                      role="region"
                      aria-label={`Preview details for ${doc.name}`}
                      className="bg-background/60 px-6 pb-4 pt-2"
                    >
                      <div className="rounded-2xl border border-border bg-card shadow-sm">
                        {expandedContent}
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}

            {hasNextPage ? (
              <div className="flex justify-center py-4">
                <button
                  type="button"
                  onClick={onLoadMore}
                  className="rounded-md text-xs font-semibold text-brand-600 transition hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:text-muted-foreground"
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
