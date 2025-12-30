import clsx from "clsx";
import { useEffect, useRef } from "react";
import type { KeyboardEvent, MouseEvent as ReactMouseEvent, ReactNode } from "react";

import type { DocumentEntry, ListDensity, WorkspacePerson } from "../types";
import { getDocumentOutputRun } from "../data";
import { fileTypeLabel, formatRelativeTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { ChatIcon, DocumentIcon, DownloadIcon, UserIcon } from "@ui/Icons";
import { MappingBadge } from "./MappingBadge";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "./PeoplePicker";
import { RowActionsMenu } from "./RowActionsMenu";
import { StatusPicker } from "./StatusPicker";
import { TagPicker } from "./TagPicker";
import { UploadProgress } from "./UploadProgress";

const INTERACTIVE_SELECTOR =
  "button, a, input, select, textarea, [role='button'], [role='menuitem'], [data-ignore-row-click='true']";

type SelectionOptions = {
  mode?: "toggle" | "range";
  checked?: boolean;
};

type DensityStyles = {
  rowGap: string;
  rowPadding: string;
  iconSize: string;
  avatarSize: string;
  pickerButtonClass: string;
};

function isInteractiveTarget(target: EventTarget | null, container?: Element | null) {
  if (!(target instanceof Element)) return false;
  const interactive = target.closest(INTERACTIVE_SELECTOR);
  if (!interactive) return false;
  if (container && interactive === container) return false;
  return true;
}

function isSelectionModifier(event: { shiftKey?: boolean; metaKey?: boolean; ctrlKey?: boolean }) {
  return Boolean(event.shiftKey || event.metaKey || event.ctrlKey);
}

function isRangeSelection(event: { shiftKey?: boolean }) {
  return Boolean(event.shiftKey);
}

function getDensityStyles(density: ListDensity): DensityStyles {
  const isCompact = density === "compact";
  return {
    rowGap: isCompact ? "gap-2" : "gap-3",
    rowPadding: isCompact ? "py-2" : "py-3",
    iconSize: isCompact ? "h-8 w-8" : "h-9 w-9",
    avatarSize: isCompact ? "h-6 w-6" : "h-7 w-7",
    pickerButtonClass: isCompact
      ? "min-w-0 max-w-[12rem] bg-background px-2 py-0.5 text-[11px] shadow-none"
      : "min-w-0 max-w-[12rem] bg-background px-2 py-1 text-[11px] shadow-none",
  };
}

export function DocumentsGrid({
  workspaceId,
  documents,
  density,
  activeId,
  selectedIds,
  onSelect,
  onSelectAll,
  onClearSelection,
  allVisibleSelected,
  someVisibleSelected,
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
  processingPaused,

  people,
  onAssign,
  onPickUp,
  onTagsChange,

  onDownloadOriginal,
  onDownloadOutput,
  onCopyLink,
  onReprocess,
  onDelete,
  onArchive,
  onRestore,
  onOpenDetails,
  onOpenNotes,
  onClosePreview,
  expandedId,
  expandedContent,
}: {
  workspaceId: string;
  documents: DocumentEntry[];
  density: ListDensity;
  activeId: string | null;
  selectedIds: Set<string>;
  onSelect: (id: string, options?: SelectionOptions) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  allVisibleSelected: boolean;
  someVisibleSelected: boolean;
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
  processingPaused: boolean;

  people: WorkspacePerson[];
  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onPickUp: (documentId: string) => void;
  onTagsChange: (documentId: string, nextTags: string[]) => void;

  onDownloadOriginal: (doc: DocumentEntry | null) => void;
  onDownloadOutput: (doc: DocumentEntry) => void;
  onCopyLink: (doc: DocumentEntry | null) => void;
  onReprocess: (doc: DocumentEntry) => void;
  onDelete: (doc: DocumentEntry) => void;
  onArchive: (doc: DocumentEntry) => void;
  onRestore: (doc: DocumentEntry) => void;
  onOpenDetails: (docId: string) => void;
  onOpenNotes: (docId: string) => void;
  onClosePreview: () => void;
  expandedId?: string | null;
  expandedContent?: ReactNode;
}) {
  const hasSelectableRows = documents.some((doc) => doc.record);
  const showLoading = isLoading && documents.length === 0;
  const showError = isError && documents.length === 0;
  const headerCheckboxRef = useRef<HTMLInputElement | null>(null);
  const densityStyles = getDensityStyles(density);

  useEffect(() => {
    if (!headerCheckboxRef.current) return;
    headerCheckboxRef.current.indeterminate = someVisibleSelected && !allVisibleSelected;
  }, [allVisibleSelected, someVisibleSelected]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-card">
      <div className="shrink-0 border-b border-border bg-background/40 px-6 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        <div
          className={clsx(
            "grid grid-cols-[auto_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.6fr)_auto] items-center",
            densityStyles.rowGap,
          )}
        >
          <div>
            <input
              type="checkbox"
              ref={headerCheckboxRef}
              checked={allVisibleSelected}
              onChange={(event) => (event.target.checked ? onSelectAll() : onClearSelection())}
              aria-label="Select all visible documents"
              disabled={!hasSelectableRows}
              className="h-4 w-4 rounded border-border-strong"
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
              const canSelectRow = Boolean(doc.record);
              const outputRun = getDocumentOutputRun(doc.record);
              const canDownloadOutput = Boolean(outputRun?.run_id);
              const isUnassigned = !doc.assigneeKey;
              const isExpanded = Boolean(expandedContent && expandedId === doc.id);
              const isActive = Boolean(isExpanded && activeId === doc.id);
              const isSelected = selectedIds.has(doc.id);
              const isArchived = doc.status === "archived";
              const previewId = `documents-preview-${doc.id}`;
              const hasNotes = doc.commentCount > 0;
              const downloadLabel = canDownloadOutput ? "Download output" : "Output not ready";
              const canEditTags = canSelectRow;
              const canEditStatus = canSelectRow;
              const handleRowClick = (event: ReactMouseEvent<HTMLDivElement>) => {
                if (isInteractiveTarget(event.target, event.currentTarget)) return;
                if (isSelectionModifier(event)) {
                  if (canSelectRow) {
                    const isRange = isRangeSelection(event);
                    onSelect(doc.id, {
                      mode: isRange ? "range" : "toggle",
                      checked: isRange ? true : !isSelected,
                    });
                  }
                  return;
                }
                onActivate(doc.id);
              };

              const handleRowKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                if (event.currentTarget !== event.target) return;
                event.preventDefault();
                onActivate(doc.id);
              };

              const handleSelectClick = (event: ReactMouseEvent<HTMLInputElement>) => {
                event.stopPropagation();
                if (!canSelectRow) return;
                const isRange = isRangeSelection(event);
                const nextChecked = !isSelected;
                onSelect(doc.id, {
                  mode: isRange ? "range" : "toggle",
                  checked: nextChecked,
                });
              };

              return (
                <div
                  key={doc.id}
                  className="border-b border-border/70"
                >
                  <div
                    role="button"
                    onClick={handleRowClick}
                    onKeyDown={handleRowKeyDown}
                    className={clsx(
                      "group grid cursor-pointer select-none grid-cols-[auto_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.6fr)_auto] items-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      densityStyles.rowGap,
                      densityStyles.rowPadding,
                      isActive
                        ? "bg-brand-50 dark:bg-brand-500/20"
                        : isSelected
                          ? "bg-muted/40 dark:bg-muted/30"
                          : "hover:bg-background dark:hover:bg-muted/40",
                    )}
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    aria-controls={isExpanded ? previewId : undefined}
                  >
                    <div>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => undefined}
                        onClick={handleSelectClick}
                        aria-label={`Select ${doc.name}`}
                        disabled={!canSelectRow}
                        className="h-4 w-4 rounded border-border-strong"
                      />
                    </div>

                    <div className="flex items-center gap-3">
                      <div
                        className={clsx(
                          "flex items-center justify-center rounded-xl border border-border bg-background",
                          densityStyles.iconSize,
                        )}
                      >
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

                    <div className="flex flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <StatusPicker
                          status={doc.status}
                          queueState={doc.queueState}
                          queueReason={doc.queueReason}
                          disabled={!canEditStatus}
                          onArchive={() => onArchive(doc)}
                          onRestore={() => onRestore(doc)}
                        />
                        <MappingBadge mapping={doc.mapping} />
                      </div>
                      {doc.upload && doc.upload.status !== "succeeded" ? <UploadProgress upload={doc.upload} /> : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={clsx(
                          "inline-flex items-center justify-center rounded-full border border-border bg-background",
                          densityStyles.avatarSize,
                        )}
                      >
                        <UserIcon className="h-4 w-4 text-muted-foreground" />
                      </span>

                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <PeoplePicker
                            people={people}
                            value={[doc.assigneeKey ?? unassignedKey()]}
                            onChange={(keys) => onAssign(doc.id, normalizeSingleAssignee(keys))}
                            placeholder="Assignee..."
                            includeUnassigned
                            buttonClassName={densityStyles.pickerButtonClass}
                          />
                          {isUnassigned ? (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onPickUp(doc.id);
                              }}
                              className="shrink-0 whitespace-nowrap text-[11px] font-semibold text-brand-600 hover:text-brand-700"
                            >
                              Assign to me
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="flex min-w-0 items-center">
                      <TagPicker
                        workspaceId={workspaceId}
                        selected={doc.tags}
                        onToggle={(tag) => {
                          const nextTags = doc.tags.includes(tag)
                            ? doc.tags.filter((t) => t !== tag)
                            : [...doc.tags, tag];
                          onTagsChange(doc.id, nextTags);
                        }}
                        placeholder="Add tags"
                        disabled={!canEditTags}
                        buttonClassName="min-w-0 max-w-[12rem] bg-background px-2 py-1 text-[11px] shadow-none"
                      />
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
                          reprocessDisabled={!doc.record || !isExpanded || processingPaused}
                          showClosePreview={isExpanded}
                          onClosePreview={onClosePreview}
                          onDownloadOriginal={() => onDownloadOriginal(doc)}
                          onCopyLink={() => onCopyLink(doc)}
                          onDelete={() => onDelete(doc)}
                          onArchive={() => onArchive(doc)}
                          onRestore={() => onRestore(doc)}
                          isArchived={isArchived}
                          originalDisabled={!doc.record}
                          copyDisabled={!doc.record}
                          deleteDisabled={!doc.record}
                          archiveDisabled={!doc.record}
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
