import clsx from "clsx";
import type { KeyboardEvent } from "react";

import type { DocumentEntry } from "../types";
import { getDocumentOutputRun } from "../data";
import { formatRelativeTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { DocumentIcon, DownloadIcon, RefreshIcon } from "./icons";
import { MappingBadge } from "./MappingBadge";
import { StatusPill } from "./StatusPill";
import { TagPicker } from "./TagPicker";

const INTERACTIVE_SELECTOR =
  "button, a, input, select, textarea, [role='button'], [role='menuitem'], [data-ignore-row-click='true']";

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest(INTERACTIVE_SELECTOR));
}

export function DocumentsGrid({
  workspaceId,
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
  onDownloadOriginal,
  onDownloadOutputFromRow,
  onReprocess,
  onToggleTagOnDocument,
}: {
  workspaceId: string;
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
  onDownloadOriginal: (doc: DocumentEntry) => void;
  onDownloadOutputFromRow: (doc: DocumentEntry) => void;
  onReprocess: (doc: DocumentEntry) => void;
  onToggleTagOnDocument: (doc: DocumentEntry, tag: string) => void;
}) {
  const hasSelectable = documents.some((doc) => doc.record);
  const showLoading = isLoading && documents.length === 0;
  const showError = isError && documents.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      <div className="border-b border-slate-200 bg-white px-6 py-2 text-xs uppercase tracking-[0.18em] text-slate-400">
        <div className="grid grid-cols-[auto_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_minmax(0,0.8fr)] items-center gap-3">
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
          <div>Output</div>
          <div>Tags</div>
          <div>Uploader</div>
          <div className="text-right">Updated</div>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto px-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
        onKeyDown={onKeyNavigate}
        tabIndex={0}
        role="list"
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
          <div className="divide-y divide-slate-100">
            {documents.map((doc) => {
              const isSelectable = Boolean(doc.record);
              const outputRun = getDocumentOutputRun(doc.record);
              const canDownloadOutput = Boolean(outputRun?.run_id);

              return (
                <div
                  key={doc.id}
                  role="listitem"
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
                    "grid cursor-pointer grid-cols-[auto_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_minmax(0,0.8fr)] items-center gap-3 py-3 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                    activeId === doc.id ? "bg-brand-50" : "hover:bg-slate-50",
                  )}
                  tabIndex={0}
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
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
                      <DocumentIcon className="h-4 w-4 text-slate-500" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {doc.name}{" "}
                        <span className="ml-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                          {doc.fileType.toUpperCase()}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        Uploaded {formatRelativeTime(now, doc.createdAt)} · {doc.size}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <StatusPill status={doc.status} />
                    <MappingBadge mapping={doc.mapping} />
                    {typeof doc.progress === "number" ? (
                      <span className="text-[11px] font-semibold text-slate-500">{Math.round(doc.progress)}%</span>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className={clsx(
                        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed",
                        canDownloadOutput
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          : "border-slate-200 bg-slate-50 text-slate-400",
                      )}
                      disabled={!canDownloadOutput}
                      onClick={(e) => {
                        e.stopPropagation();
                        onDownloadOutputFromRow(doc);
                      }}
                      title={canDownloadOutput ? "Download processed output" : "Output not ready (open preview to see runs)"}
                    >
                      <DownloadIcon className="h-4 w-4" />
                      Download
                    </button>

                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-400"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDownloadOriginal(doc);
                      }}
                      disabled={!doc.record}
                      title="Download original upload"
                    >
                      <DownloadIcon className="h-4 w-4" />
                      Original
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <TagPicker
                      workspaceId={workspaceId}
                      selected={doc.tags}
                      onToggle={(tag) => onToggleTagOnDocument(doc, tag)}
                      placeholder={doc.tags.length ? "Edit tags" : "Add tags"}
                      disabled={!doc.record}
                    />
                  </div>

                  <div className="text-xs font-semibold text-slate-500">{doc.uploader ?? "Unassigned"}</div>

                  <div className="flex items-center justify-end gap-2">
                    <div className="text-right text-xs text-slate-500">{formatRelativeTime(now, doc.updatedAt)}</div>

                    <button
                      type="button"
                      className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-300"
                      onClick={(e) => {
                        e.stopPropagation();
                        onReprocess(doc);
                      }}
                      disabled={!doc.record}
                      title="Reprocess (create new run)"
                      aria-label={`Reprocess ${doc.name}`}
                    >
                      <RefreshIcon className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}

            {hasNextPage ? (
              <div className="flex justify-center py-4">
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
        )}
      </div>
    </div>
  );
}
