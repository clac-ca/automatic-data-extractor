import { useEffect, useMemo, useRef, useState } from "react";

import clsx from "clsx";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSearchParams } from "@app/nav/urlState";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { apiFetch, buildApiHeaders, client, resolveApiUrl } from "@shared/api/client";
import { DEFAULT_PAGE_SIZE, useFlattenedPages } from "@shared/api/pagination";
import { patchDocumentTags, replaceDocumentTags } from "@shared/documents/tags";
import { uploadWorkspaceDocument } from "@shared/documents/uploads";
import { fetchRun, runOutputUrl, runQueryKeys, type RunResource } from "@shared/runs/api";
import type { components, paths } from "@schema";

import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type DocumentListPage = components["schemas"]["DocumentPage"];
type RunOutput = components["schemas"]["RunOutput"];
type RunStatus = components["schemas"]["RunStatus"];
type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

type UiDocumentStatus = "uploaded" | "processing" | "ready" | "failed" | "archived";

type QueueId = "all" | "needs-attention" | "in-progress" | "ready" | "failed";

type SavedViewId = "quarter-close" | "finance-ready" | "vendor-ops";

type QueueSelection =
  | { readonly kind: "queue"; readonly id: QueueId }
  | { readonly kind: "saved"; readonly id: SavedViewId };

interface DocumentHistoryItem {
  readonly label: string;
  readonly timestamp: string;
  readonly tone: "success" | "warning" | "error" | "neutral";
}

type OutputPreview =
  | { readonly kind: "table"; readonly columns: readonly string[]; readonly rows: readonly string[][] }
  | { readonly kind: "json"; readonly snippet: string }
  | { readonly kind: "pdf" }
  | { readonly kind: "unsupported"; readonly reason: string };

interface SavedView {
  readonly id: SavedViewId;
  readonly name: string;
  readonly description: string;
  readonly query: Partial<ListDocumentsQuery>;
}

interface OptionsMenuItem {
  readonly label: string;
  readonly description?: string;
  readonly disabled?: boolean;
  readonly onSelect?: () => void;
}

type OutputFormat = "csv" | "json" | "pdf" | "xlsx" | "unknown";

type QueueDefinition = {
  readonly id: QueueId;
  readonly label: string;
  readonly query: Partial<ListDocumentsQuery>;
};

const ACTIVE_STATUSES: readonly DocumentStatus[] = [
  "uploaded",
  "processing",
  "processed",
  "failed",
];

const MIN_SEARCH_LENGTH = 2;
const MAX_PREVIEW_BYTES = 750_000;
const MAX_DOCUMENT_TAGS = 50;
const DEFAULT_SORT = "-last_run_at,-created_at";

const QUEUES: readonly QueueDefinition[] = [
  { id: "all", label: "All", query: { status_in: [...ACTIVE_STATUSES] } },
  { id: "needs-attention", label: "Needs attention", query: { status_in: ["failed"] } },
  { id: "in-progress", label: "In progress", query: { status_in: ["uploaded", "processing"] } },
  { id: "ready", label: "Ready", query: { status_in: ["processed"] } },
  { id: "failed", label: "Failed", query: { status_in: ["failed"] } },
];

const SAVED_VIEWS: readonly SavedView[] = [
  {
    id: "quarter-close",
    name: "Quarter Close QA",
    description: "Finance documents that are still running or failed.",
    query: {
      status_in: ["uploaded", "processing", "failed"],
      tags: ["Finance"],
      tags_match: "any",
    },
  },
  {
    id: "finance-ready",
    name: "Finance Ready",
    description: "Processed finance outputs ready for review.",
    query: {
      status_in: ["processed"],
      tags: ["Finance"],
      tags_match: "any",
    },
  },
  {
    id: "vendor-ops",
    name: "Vendor Ops",
    description: "Operational vendor docs to sync back.",
    query: {
      status_in: [...ACTIVE_STATUSES],
      tags: ["Vendors", "Ops"],
      tags_match: "any",
    },
  },
];

const STATUS_META: Record<
  UiDocumentStatus,
  { label: string; dot: string; text: string; badge: string; icon: (props: { className?: string }) => JSX.Element }
> = {
  uploaded: {
    label: "Uploaded",
    dot: "bg-muted-foreground",
    text: "text-muted-foreground",
    badge: "bg-muted text-muted-foreground",
    icon: ({ className }) => (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
        <path d="M10 13V4" strokeLinecap="round" />
        <path d="m6 8 4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 13v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2" strokeLinecap="round" />
      </svg>
    ),
  },
  processing: {
    label: "Processing",
    dot: "bg-sky-500",
    text: "text-sky-700",
    badge: "bg-sky-100 text-sky-700",
    icon: ({ className }) => (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
        <path d="M4 10a6 6 0 0 0 10.5 4" strokeLinecap="round" />
        <path d="M16 10a6 6 0 0 0-10.5-4" strokeLinecap="round" />
        <path d="M5 4v4h4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  ready: {
    label: "Ready",
    dot: "bg-emerald-500",
    text: "text-emerald-700",
    badge: "bg-emerald-100 text-emerald-700",
    icon: ({ className }) => (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
        <path d="m5 10 3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 10a6 6 0 1 1 12 0" strokeLinecap="round" />
      </svg>
    ),
  },
  failed: {
    label: "Failed",
    dot: "bg-rose-500",
    text: "text-rose-700",
    badge: "bg-rose-100 text-rose-700",
    icon: ({ className }) => (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
        <path d="M6 6l8 8" strokeLinecap="round" />
        <path d="M14 6l-8 8" strokeLinecap="round" />
        <path d="M4 10a6 6 0 1 1 12 0" strokeLinecap="round" />
      </svg>
    ),
  },
  archived: {
    label: "Archived",
    dot: "bg-muted",
    text: "text-muted-foreground",
    badge: "bg-muted text-muted-foreground",
    icon: ({ className }) => (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
        <path d="M6 8h8" strokeLinecap="round" />
        <path d="M4 6h12v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6Z" strokeLinecap="round" />
        <path d="M6 4h8" strokeLinecap="round" />
      </svg>
    ),
  },
};

const EMPTY_STATES: Record<QueueId, { title: string; description: string }> = {
  all: {
    title: "No documents yet",
    description: "Upload a document to start a run. Outputs will appear here as they complete.",
  },
  "needs-attention": {
    title: "No documents need attention",
    description: "Everything is processing smoothly. We'll call out any issues here.",
  },
  "in-progress": {
    title: "Nothing in progress",
    description: "New uploads and running jobs will show up in this queue.",
  },
  ready: {
    title: "No documents are ready",
    description: "Finished outputs will land here once processing is complete.",
  },
  failed: {
    title: "No failed documents",
    description: "Great news - there are no failures in the queue right now.",
  },
};

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

export default function WorkspaceDocumentsV2Route() {
  const { workspace } = useWorkspaceContext();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const rawSearchQuery = searchParams.get("q")?.trim() ?? "";

  const [queueSelection, setQueueSelection] = useState<QueueSelection>({ kind: "queue", id: "all" });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  const [searchValue, setSearchValue] = useState(rawSearchQuery);
  const [uploadState, setUploadState] = useState<{
    readonly status: "idle" | "uploading" | "done" | "error";
    readonly total?: number;
    readonly completed?: number;
    readonly currentFile?: string;
    readonly progress?: number | null;
    readonly error?: string;
  }>({ status: "idle" });
  const [bulkTagMode, setBulkTagMode] = useState(false);
  const [bulkTagValue, setBulkTagValue] = useState("");
  const [bulkTagError, setBulkTagError] = useState<string | null>(null);

  const trimmedSearchValue = searchValue.trim();
  const searchActive = rawSearchQuery.length >= MIN_SEARCH_LENGTH;
  const searchTooShort = trimmedSearchValue.length > 0 && trimmedSearchValue.length < MIN_SEARCH_LENGTH;
  const searchQuery = searchActive ? rawSearchQuery : "";

  useEffect(() => {
    setSearchValue(rawSearchQuery);
  }, [rawSearchQuery]);

  useEffect(() => {
    const nextQuery = trimmedSearchValue.length >= MIN_SEARCH_LENGTH ? trimmedSearchValue : "";
    if (nextQuery === rawSearchQuery) {
      return;
    }
    const handle = window.setTimeout(() => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (nextQuery) {
          next.set("q", nextQuery);
        } else {
          next.delete("q");
        }
        return next;
      });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [rawSearchQuery, setSearchParams, trimmedSearchValue]);

  const listQuery = useMemo(
    () => buildListQuery(queueSelection, searchQuery),
    [queueSelection, searchQuery],
  );
  const listQueryKey = useMemo(() => JSON.stringify(listQuery), [listQuery]);

  const documentsQuery = useInfiniteQuery<DocumentListPage>({
    queryKey: ["documents-v2", workspace.id, listQueryKey],
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspace.id,
        {
          ...listQuery,
          page: typeof pageParam === "number" ? pageParam : 1,
          page_size: DEFAULT_PAGE_SIZE,
        },
        signal,
      ),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: workspace.id.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 15_000,
  });

  const documents = useFlattenedPages(documentsQuery.data?.pages, (doc) => doc.id);
  const documentTotal = documentsQuery.data?.pages?.[0]?.total;
  const hasDocumentTotal = typeof documentTotal === "number";
  const documentCountLabel = (
    hasDocumentTotal ? documentTotal : documents.length
  ).toLocaleString();
  const documentCountSummary =
    hasDocumentTotal && documents.length < documentTotal
      ? `${documents.length.toLocaleString()} of ${documentTotal.toLocaleString()}`
      : documentCountLabel;

  const needsAttentionQuery = useQuery({
    queryKey: ["documents-v2", workspace.id, "needs-attention-count"],
    queryFn: ({ signal }) =>
      fetchDocumentsCount(
        workspace.id,
        {
          status_in: ["failed"],
        },
        signal,
      ),
    enabled: workspace.id.length > 0,
    staleTime: 30_000,
  });
  const needsAttentionCount = needsAttentionQuery.data ?? 0;

  const activeQueueId = queueSelection.kind === "queue" ? queueSelection.id : null;
  const activeSavedView =
    queueSelection.kind === "saved" ? SAVED_VIEWS.find((view) => view.id === queueSelection.id) ?? null : null;
  const listContextLabel = searchQuery
    ? `Filtered by "${searchQuery}"`
    : searchTooShort
      ? `Search requires at least ${MIN_SEARCH_LENGTH} characters`
      : "Sorted by recent activity";

  useEffect(() => {
    setSelectedIds(new Set());
  }, [queueSelection, searchQuery]);

  useEffect(() => {
    if (documents.length === 0) {
      setActiveDocumentId(null);
      return;
    }
    setActiveDocumentId((current) => {
      if (current && documents.some((doc) => doc.id === current)) {
        return current;
      }
      return documents[0].id;
    });
  }, [documents]);

  const activeDocument = useMemo(
    () => documents.find((doc) => doc.id === activeDocumentId) ?? null,
    [activeDocumentId, documents],
  );

  const selectedIdsArray = useMemo(() => Array.from(selectedIds), [selectedIds]);
  const allVisibleSelected = documents.length > 0 && documents.every((doc) => selectedIds.has(doc.id));
  const someVisibleSelected = documents.some((doc) => selectedIds.has(doc.id));

  const emptyState = queueSelection.kind === "queue" ? EMPTY_STATES[queueSelection.id] : null;
  const bulkTagMutation = useMutation({
    mutationFn: async ({ documentIds, tags }: { documentIds: readonly string[]; tags: string[] }) => {
      await Promise.all(
        documentIds.map((documentId) =>
          patchDocumentTags(workspace.id, documentId, { add: tags }),
        ),
      );
    },
    onSuccess: () => {
      setBulkTagMode(false);
      setBulkTagValue("");
      setBulkTagError(null);
      queryClient.invalidateQueries({ queryKey: ["documents-v2", workspace.id] });
    },
    onError: (error) => {
      setBulkTagError(resolveErrorMessage(error, "Unable to update tags."));
    },
  });
  const uploadStatusMessage = useMemo(() => {
    if (uploadState.status === "uploading") {
      const completed = uploadState.completed ?? 0;
      const total = uploadState.total ?? 0;
      const current = total > 0 ? Math.min(completed + 1, total) : 0;
      const fileName = uploadState.currentFile ? ` ${uploadState.currentFile}` : "";
      const progress = uploadState.progress != null ? ` (${uploadState.progress}%)` : "";
      return total > 0
        ? `Uploading${fileName} ${current}/${total}${progress}`
        : `Uploading${fileName}${progress}`;
    }
    if (uploadState.status === "done") {
      const total = uploadState.total ?? 0;
      return total > 0 ? `Uploaded ${total} file${total === 1 ? "" : "s"}` : "Upload complete";
    }
    if (uploadState.status === "error") {
      return uploadState.error ?? "Upload failed";
    }
    return null;
  }, [uploadState]);

  useEffect(() => {
    if (selectedIdsArray.length === 0) {
      setBulkTagMode(false);
      setBulkTagValue("");
      setBulkTagError(null);
    }
  }, [selectedIdsArray.length]);

  const handleBulkTagSave = () => {
    const tags = normalizeTags(splitTagInput(bulkTagValue));
    if (tags.length === 0) {
      setBulkTagError("Enter at least one tag.");
      return;
    }
    if (tags.length > MAX_DOCUMENT_TAGS) {
      setBulkTagError(`Tag limit reached (${MAX_DOCUMENT_TAGS} max).`);
      return;
    }
    setBulkTagError(null);
    bulkTagMutation.mutate({ documentIds: selectedIdsArray, tags });
  };

  const handleUploadClick = () => {
    if (uploadState.status === "uploading") {
      return;
    }
    uploadInputRef.current?.click();
  };

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0 || uploadState.status === "uploading") {
      return;
    }
    const fileList = Array.from(files);
    setUploadState({
      status: "uploading",
      total: fileList.length,
      completed: 0,
      currentFile: fileList[0]?.name,
      progress: 0,
    });

    for (let index = 0; index < fileList.length; index += 1) {
      const file = fileList[index];
      try {
        const handle = uploadWorkspaceDocument(workspace.id, file, {
          onProgress: (progress) => {
            setUploadState((current) => ({
              ...current,
              status: "uploading",
              progress: progress.percent,
              currentFile: file.name,
            }));
          },
        });
        await handle.promise;
        setUploadState((current) => ({
          ...current,
          status: "uploading",
          completed: index + 1,
          currentFile: fileList[index + 1]?.name,
          progress: null,
        }));
      } catch (error) {
        setUploadState({
          status: "error",
          total: fileList.length,
          completed: index,
          currentFile: file.name,
          error: resolveErrorMessage(error, "Upload failed. Please try again."),
        });
        break;
      }
    }

    queryClient.invalidateQueries({ queryKey: ["documents-v2", workspace.id] });
    setUploadState((current) =>
      current.status === "error"
        ? current
        : {
            status: "done",
            total: fileList.length,
            completed: fileList.length,
          },
    );
    window.setTimeout(() => {
      setUploadState((current) => (current.status === "error" ? current : { status: "idle" }));
    }, 2500);
  };

  return (
    <section className="relative flex min-h-0 flex-1 min-w-0 flex-col gap-6 px-4 py-6 lg:flex-row lg:gap-8 lg:px-8">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-background via-card to-muted" />
        <div className="absolute -left-10 top-6 h-40 w-40 rounded-full bg-sky-100/70 blur-3xl" />
        <div className="absolute right-6 top-20 h-52 w-52 rounded-full bg-emerald-100/70 blur-3xl" />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
        <header className="flex flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-foreground px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-background">
                  Documents v2
                </span>
                {activeSavedView ? (
                  <span className="text-xs font-semibold text-emerald-700">View: {activeSavedView.name}</span>
                ) : null}
              </div>
              <h1 className="text-2xl font-semibold text-foreground">Document workspace</h1>
              <p className="text-sm text-muted-foreground">
                {documentCountSummary} documents - outcomes and exceptions surfaced in real time.
              </p>
              {activeSavedView ? (
                <p className="text-xs font-semibold text-emerald-700">{activeSavedView.description}</p>
              ) : null}
              {uploadStatusMessage ? (
                <p
                  className={clsx(
                    "text-xs font-semibold",
                    uploadState.status === "error" ? "text-rose-600" : "text-muted-foreground",
                  )}
                >
                  {uploadStatusMessage}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" disabled>
                New view
              </Button>
              <Button size="sm" onClick={handleUploadClick} disabled={uploadState.status === "uploading"}>
                Upload
              </Button>
            </div>
          </div>
          <QueueBar
            activeQueueId={activeQueueId}
            queueSelection={queueSelection}
            needsAttentionCount={needsAttentionCount}
            onSelectQueue={(id) => setQueueSelection({ kind: "queue", id })}
            onSelectSavedView={(id) => setQueueSelection({ kind: "saved", id })}
          />
        </header>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border/80 bg-card/90 shadow-[0_28px_60px_-45px_rgb(var(--color-shadow)/0.55)]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">Queue</span>
              <span>-</span>
              <span>
                {queueSelection.kind === "queue"
                  ? QUEUES.find((queue) => queue.id === queueSelection.id)?.label
                  : activeSavedView?.name}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <SearchField
                value={searchValue}
                onChange={setSearchValue}
                onClear={() => setSearchValue("")}
              />
              <div className="text-xs text-muted-foreground">{listContextLabel}</div>
            </div>
          </div>

          <div className="relative flex min-h-0 flex-1 flex-col">
            <BulkActionOverlay
              visibleCount={selectedIdsArray.length}
              tagMode={bulkTagMode}
              tagValue={bulkTagValue}
              tagError={bulkTagError}
              tagBusy={bulkTagMutation.isPending}
              onChangeTagValue={setBulkTagValue}
              onStartTag={() => {
                setBulkTagMode(true);
                setBulkTagError(null);
              }}
              onCancelTag={() => {
                setBulkTagMode(false);
                setBulkTagValue("");
                setBulkTagError(null);
              }}
              onSaveTag={handleBulkTagSave}
              onClear={() => setSelectedIds(new Set())}
            />
            <div
              className={clsx(
                "min-h-0 flex-1 overflow-y-auto",
                selectedIdsArray.length > 0 ? "pt-12" : "",
              )}
            >
              {documentsQuery.isLoading ? (
                <TableSkeleton />
              ) : documentsQuery.isError ? (
                <div className="p-6 text-sm text-rose-600">
                  Unable to load documents. Please try again.
                </div>
              ) : documents.length === 0 ? (
                <EmptyState
                  title={
                    emptyState?.title ?? `No documents match ${activeSavedView?.name ?? "this view"}`
                  }
                  description={
                    emptyState?.description ??
                    activeSavedView?.description ??
                    "Try selecting another queue or adjusting the search terms."
                  }
                />
              ) : (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 z-0 bg-background/95 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="w-10 px-3 py-2 text-left">
                        <SelectAllCheckbox
                          checked={allVisibleSelected}
                          indeterminate={someVisibleSelected && !allVisibleSelected}
                          onChange={() => {
                            setSelectedIds((current) => {
                              if (allVisibleSelected) {
                                return new Set();
                              }
                              const next = new Set(current);
                              documents.forEach((doc) => next.add(doc.id));
                              return next;
                            });
                          }}
                        />
                      </th>
                      <th className="px-3 py-2 text-left">Document</th>
                      <th className="px-3 py-2 text-left">Tags</th>
                      <th className="px-3 py-2 text-left">Updated</th>
                      <th className="px-3 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => {
                      const statusMeta = STATUS_META[toUiStatus(doc.status)];
                      const active = doc.id === activeDocumentId;
                      const tags = (doc.tags ?? []).slice(0, 2);
                      const overflow = (doc.tags ?? []).length - tags.length;
                      const needsAttention = isNeedsAttention(doc);
                      const updatedAt = resolveDocumentActivityTime(doc);

                      return (
                        <tr
                          key={doc.id}
                          className={clsx(
                            "border-b border-border transition-colors",
                            active ? "bg-muted/70" : "hover:bg-background",
                          )}
                          onClick={() => setActiveDocumentId(doc.id)}
                        >
                          <td className="px-3 py-2" onClick={(event) => event.stopPropagation()}>
                            <RowCheckbox
                              checked={selectedIds.has(doc.id)}
                              onChange={() => {
                                setSelectedIds((current) => {
                                  const next = new Set(current);
                                  if (next.has(doc.id)) {
                                    next.delete(doc.id);
                                  } else {
                                    next.add(doc.id);
                                  }
                                  return next;
                                });
                              }}
                            />
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-2">
                              <FileIcon className="h-4 w-4 text-muted-foreground" />
                              <span className="font-medium text-foreground">{doc.name}</span>
                              {needsAttention ? (
                                <span
                                  className="inline-flex h-2 w-2 rounded-full bg-amber-400"
                                  title="Needs attention"
                                  aria-label="Needs attention"
                                />
                              ) : null}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap items-center gap-1">
                              {tags.length ? (
                                tags.map((tag) => (
                                  <span
                                    key={tag}
                                    className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                                  >
                                    {tag}
                                  </span>
                                ))
                              ) : (
                                <span className="text-xs text-muted-foreground">No tags</span>
                              )}
                              {overflow > 0 ? <span className="text-xs text-muted-foreground">+{overflow}</span> : null}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-xs text-muted-foreground">{formatRelativeTime(updatedAt)}</td>
                          <td className="px-3 py-2">
                            <div className={clsx("flex items-center gap-2 text-xs font-semibold", statusMeta.text)}>
                              <span className={clsx("h-2.5 w-2.5 rounded-full", statusMeta.dot)} />
                              {statusMeta.label}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
            {documentsQuery.hasNextPage ? (
              <div className="flex justify-center border-t border-border bg-background/60 px-3 py-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => documentsQuery.fetchNextPage()}
                  disabled={documentsQuery.isFetchingNextPage}
                >
                  {documentsQuery.isFetchingNextPage ? "Loading more documents..." : "Load more documents"}
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <aside className="flex min-h-[18rem] w-full flex-col overflow-hidden rounded-2xl border border-border/80 bg-card/95 shadow-[0_32px_70px_-50px_rgb(var(--color-shadow)/0.6)] lg:w-[min(28rem,38vw)]">
        <DocumentInspector workspaceId={workspace.id} document={activeDocument} />
      </aside>
      <input
        ref={uploadInputRef}
        type="file"
        className="sr-only"
        multiple
        onChange={(event) => {
          void handleFilesSelected(event.target.files);
          event.target.value = "";
        }}
      />
    </section>
  );
}

interface QueueBarProps {
  readonly activeQueueId: QueueId | null;
  readonly queueSelection: QueueSelection;
  readonly needsAttentionCount: number;
  readonly onSelectQueue: (id: QueueId) => void;
  readonly onSelectSavedView: (id: SavedViewId) => void;
}

function QueueBar({
  activeQueueId,
  queueSelection,
  needsAttentionCount,
  onSelectQueue,
  onSelectSavedView,
}: QueueBarProps) {
  const savedViewActive = queueSelection.kind === "saved";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {QUEUES.map((queue) => {
          const active = activeQueueId === queue.id && !savedViewActive;
          const showCount = queue.id === "needs-attention";
          return (
            <button
              key={queue.id}
              type="button"
              className={clsx(
                "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold transition",
                active
                  ? "bg-foreground text-background"
                  : "bg-card text-muted-foreground hover:bg-muted",
              )}
              onClick={() => onSelectQueue(queue.id)}
            >
              {queue.label}
              {showCount ? (
                <span
                  className={clsx(
                    "rounded-full px-2 py-0.5 text-xs font-semibold",
                    active ? "bg-card/20 text-white" : "bg-amber-100 text-amber-700",
                  )}
                >
                  {needsAttentionCount}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      <div className="flex-1" />
      <SavedViewsMenu
        activeViewId={queueSelection.kind === "saved" ? queueSelection.id : null}
        onSelectView={onSelectSavedView}
      />
    </div>
  );
}

interface SavedViewsMenuProps {
  readonly activeViewId: SavedViewId | null;
  readonly onSelectView: (id: SavedViewId) => void;
}

function SavedViewsMenu({ activeViewId, onSelectView }: SavedViewsMenuProps) {
  const menuRef = useRef<HTMLDetailsElement | null>(null);
  const activeView = SAVED_VIEWS.find((view) => view.id === activeViewId);

  return (
    <details
      ref={menuRef}
      className={clsx(
        "relative rounded-full border border-border bg-card text-sm",
        activeView ? "border-emerald-200 bg-emerald-50/70" : "",
      )}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full px-3 py-1.5 font-semibold text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background [&::-webkit-details-marker]:hidden [&::marker]:hidden">
        <span>{activeView ? activeView.name : "Saved views"}</span>
        <ChevronIcon className="h-4 w-4" />
      </summary>
      <div className="absolute right-0 top-[calc(100%+0.5rem)] z-20 w-72 rounded-2xl border border-border bg-card p-3 shadow-xl">
        <div className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Saved views</div>
        <div className="space-y-1">
          {SAVED_VIEWS.map((view) => (
            <button
              key={view.id}
              type="button"
              className={clsx(
                "flex w-full flex-col gap-1 rounded-xl px-3 py-2 text-left text-sm transition",
                view.id === activeViewId ? "bg-emerald-50 text-emerald-700" : "hover:bg-background",
              )}
              onClick={() => {
                onSelectView(view.id);
                if (menuRef.current) {
                  menuRef.current.open = false;
                }
              }}
            >
              <span className="font-semibold text-foreground">{view.name}</span>
              <span className="text-xs text-muted-foreground">{view.description}</span>
            </button>
          ))}
        </div>
      </div>
    </details>
  );
}

interface BulkActionOverlayProps {
  readonly visibleCount: number;
  readonly tagMode: boolean;
  readonly tagValue: string;
  readonly tagError: string | null;
  readonly tagBusy: boolean;
  readonly onChangeTagValue: (value: string) => void;
  readonly onStartTag: () => void;
  readonly onCancelTag: () => void;
  readonly onSaveTag: () => void;
  readonly onClear: () => void;
}

function BulkActionOverlay({
  visibleCount,
  tagMode,
  tagValue,
  tagError,
  tagBusy,
  onChangeTagValue,
  onStartTag,
  onCancelTag,
  onSaveTag,
  onClear,
}: BulkActionOverlayProps) {
  return (
    <div
      className={clsx(
        "pointer-events-none absolute left-0 right-0 top-0 z-10 flex items-center justify-between border-b border-border/70 bg-background/95 px-4 py-2 text-sm transition-opacity",
        visibleCount > 0 ? "opacity-100" : "opacity-0",
      )}
      aria-hidden={visibleCount === 0}
    >
      <div className="pointer-events-auto flex w-full flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-foreground">{visibleCount} selected</span>
          {tagMode ? (
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-[12rem]">
                <Input
                  value={tagValue}
                  onChange={(event) => onChangeTagValue(event.target.value)}
                  placeholder="Add tags (comma separated)"
                  disabled={tagBusy}
                  invalid={Boolean(tagError)}
                />
              </div>
              <Button size="sm" onClick={onSaveTag} disabled={tagBusy}>
                Apply tags
              </Button>
              <Button size="sm" variant="secondary" onClick={onCancelTag} disabled={tagBusy}>
                Cancel
              </Button>
              {tagError ? <span className="text-xs text-rose-600">{tagError}</span> : null}
            </div>
          ) : (
            <>
              <button
                type="button"
                className="rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground"
                disabled
                title="Retry runs is coming soon."
              >
                Retry
              </button>
              <button
                type="button"
                className="rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground"
                onClick={onStartTag}
              >
                Tag
              </button>
              <button
                type="button"
                className="rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground"
                disabled
                title="Archive is not available yet."
              >
                Archive
              </button>
            </>
          )}
        </div>
        <button
          type="button"
          className="rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground"
          onClick={onClear}
          disabled={tagBusy}
        >
          Clear
        </button>
      </div>
    </div>
  );
}

function EmptyState({ title, description }: { readonly title: string; readonly description: string }) {
  return (
    <div className="flex min-h-[16rem] flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <InboxIcon className="h-6 w-6" />
      </div>
      <div>
        <p className="text-base font-semibold text-foreground">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="p-6 text-sm text-muted-foreground">
      Loading documents...
    </div>
  );
}

function SearchField({
  value,
  onChange,
  onClear,
}: {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly onClear: () => void;
}) {
  return (
    <div className="relative w-60">
      <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && value) {
            event.preventDefault();
            onClear();
          }
        }}
        placeholder="Search documents"
        className="pl-9 pr-8"
        aria-label="Search documents"
      />
      {value ? (
        <button
          type="button"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-semibold text-muted-foreground hover:text-muted-foreground"
          onClick={onClear}
          aria-label="Clear search"
        >
          x
        </button>
      ) : null}
    </div>
  );
}

function OptionsMenu({
  label,
  items,
}: {
  readonly label: string;
  readonly items: readonly OptionsMenuItem[];
}) {
  const menuRef = useRef<HTMLDetailsElement | null>(null);

  if (items.length === 0) {
    return (
      <button
        type="button"
        className="rounded-full border border-emerald-200 bg-card px-3 py-1 text-xs font-semibold text-emerald-300"
        disabled
      >
        {label}
      </button>
    );
  }

  return (
    <details ref={menuRef} className="relative">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full border border-emerald-200 bg-card px-3 py-1 text-xs font-semibold text-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background [&::-webkit-details-marker]:hidden [&::marker]:hidden">
        <span>{label}</span>
        <ChevronIcon className="h-4 w-4" />
      </summary>
      <div className="absolute right-0 top-[calc(100%+0.5rem)] z-20 w-56 rounded-2xl border border-border bg-card p-2 shadow-xl">
        <div className="space-y-1">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              className={clsx(
                "flex w-full flex-col gap-0.5 rounded-xl px-3 py-2 text-left text-sm transition",
                item.disabled ? "cursor-not-allowed text-muted-foreground" : "text-muted-foreground hover:bg-background",
              )}
              onClick={() => {
                if (item.disabled) {
                  return;
                }
                item.onSelect?.();
                if (menuRef.current) {
                  menuRef.current.open = false;
                }
              }}
              disabled={item.disabled}
            >
              <span className="font-semibold text-foreground">{item.label}</span>
              {item.description ? (
                <span className="text-xs text-muted-foreground">{item.description}</span>
              ) : null}
            </button>
          ))}
        </div>
      </div>
    </details>
  );
}

function DocumentInspector({
  workspaceId,
  document,
}: {
  readonly workspaceId: string;
  readonly document: DocumentRecord | null;
}) {
  const previewContainerRef = useRef<HTMLDivElement | null>(null);
  const runId = document?.last_run?.run_id ?? null;
  const runQuery = useQuery({
    queryKey: runId ? runQueryKeys.detail(runId) : ["run", "none"],
    queryFn: ({ signal }) => (runId ? fetchRun(runId, signal) : Promise.reject(new Error("No run selected"))),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "queued" ? 2000 : false;
    },
    staleTime: 10_000,
  });
  const run = runQuery.data ?? null;
  const outputMeta = run?.output ?? null;
  const outputDownloadUrl = run ? runOutputUrl(run) : null;
  const outputReady = Boolean(outputMeta?.ready && outputDownloadUrl);
  const outputFilename = outputMeta ? resolveOutputFilename(outputMeta) : "Processed output";
  const outputFormat = outputMeta ? inferOutputFormat(outputMeta) : "unknown";
  const outputSize = outputMeta?.size_bytes ? formatBytes(outputMeta.size_bytes) : "Unknown size";
  const previewCapability = outputMeta ? resolvePreviewCapability(outputMeta) : null;
  const outputStatusLabel = resolveOutputStatusLabel(run, outputReady, outputMeta);
  const outputStatusTone = outputReady
    ? "bg-emerald-100 text-emerald-700"
    : run?.status === "failed"
      ? "bg-rose-100 text-rose-700"
      : run?.status === "cancelled"
        ? "bg-muted text-muted-foreground"
        : "bg-amber-100 text-amber-700";

  const previewAvailable = Boolean(outputReady && previewCapability?.kind !== "unsupported");
  const previewQuery = useQuery<OutputPreview>({
    queryKey: ["documents-v2", "preview", run?.id ?? "none", outputMeta?.filename ?? ""],
    queryFn: ({ signal }) => {
      if (!run || !outputMeta) {
        return Promise.reject(new Error("Missing run output."));
      }
      return fetchOutputPreview(run, outputMeta, signal);
    },
    enabled: Boolean(outputReady && previewCapability?.kind === "data"),
    staleTime: 60_000,
  });

  const previewErrorMessage = previewQuery.isError
    ? "Unable to load preview. Download the output to review it."
    : null;

  if (!document) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <SearchIcon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-base font-semibold text-foreground">Select a document</p>
          <p className="text-sm text-muted-foreground">Choose a row to review status, output, and history.</p>
        </div>
      </div>
    );
  }

  const originalDownloadUrl = resolveApiUrl(
    `/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`,
  );
  const uiStatus = toUiStatus(document.status);
  const statusMeta = STATUS_META[uiStatus];
  const statusDetail = formatStatusDetail(document, run);
  const historyItems = buildDocumentHistory(document, run);
  const outputMenuItems: OptionsMenuItem[] = [
    {
      label: "Open processed in new tab",
      disabled: !outputReady,
      onSelect: () => {
        if (outputDownloadUrl) {
          window.open(outputDownloadUrl, "_blank", "noopener,noreferrer");
        }
      },
    },
    {
      label: "Download original",
      onSelect: () => {
        window.open(originalDownloadUrl, "_blank", "noopener,noreferrer");
      },
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border/80 px-5 py-4">
        <div className="flex items-start gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Summary</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">{document.name}</h2>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className={clsx("inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold", statusMeta.badge)}>
            {statusMeta.icon({ className: "h-4 w-4" })}
            {statusDetail}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-muted-foreground">
          <div>
            <p className="text-xs uppercase text-muted-foreground">Uploaded</p>
            <p className="font-semibold text-foreground">{formatRelativeTime(document.created_at)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-muted-foreground">Uploader</p>
            <p className="font-semibold text-foreground">{formatUploaderLabel(document)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-muted-foreground">File size</p>
            <p className="font-semibold text-foreground">{formatBytes(document.byte_size)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-muted-foreground">Updated</p>
            <p className="font-semibold text-foreground">{formatRelativeTime(resolveDocumentActivityTime(document, run))}</p>
          </div>
        </div>
        <div className="mt-4">
          <TagEditor workspaceId={workspaceId} document={document} />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-5 py-5">
        <section className="rounded-2xl border border-emerald-200/70 bg-emerald-50/60 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Outcome</p>
              <h3 className="text-lg font-semibold text-foreground">Processed output</h3>
            </div>
            <span className="text-xs font-semibold text-emerald-700">Primary</span>
          </div>
          {outputMeta ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-100/80 bg-card/80 px-3 py-2">
              <div>
                <p className="text-sm font-semibold text-foreground">{outputFilename}</p>
                <p className="text-xs text-muted-foreground">
                  {formatOutputLabel(outputFormat)} - {outputSize}
                </p>
              </div>
              <span className={clsx("rounded-full px-2.5 py-1 text-xs font-semibold", outputStatusTone)}>
                {outputStatusLabel}
              </span>
            </div>
          ) : (
            <div className="mt-3 rounded-xl border border-amber-200/70 bg-amber-50/70 px-3 py-2 text-sm text-amber-800">
              {document.status === "failed"
                ? "Output is unavailable for failed runs."
                : "Output will appear after processing completes."}
            </div>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              disabled={!previewAvailable}
              onClick={() => {
                if (previewCapability?.kind === "pdf" && outputDownloadUrl) {
                  window.open(outputDownloadUrl, "_blank", "noopener,noreferrer");
                  return;
                }
                previewContainerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
              title={previewCapability?.kind === "pdf" ? "Open PDF preview" : "Jump to preview panel"}
            >
              {previewCapability?.kind === "pdf" ? "Open PDF preview" : "Preview processed"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!outputReady}
              onClick={() => {
                if (outputDownloadUrl) {
                  window.open(outputDownloadUrl, "_blank", "noopener,noreferrer");
                }
              }}
            >
              Download processed
            </Button>
            <OptionsMenu label="More options" items={outputMenuItems} />
          </div>
          <div ref={previewContainerRef} className="mt-4 rounded-xl border border-emerald-100/80 bg-card/80 p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Preview</p>
              {outputDownloadUrl ? (
                <button
                  type="button"
                  className="text-xs font-semibold text-emerald-700"
                  onClick={() => window.open(outputDownloadUrl, "_blank", "noopener,noreferrer")}
                >
                  Full screen
                </button>
              ) : (
                <span className="text-xs text-muted-foreground">Full screen</span>
              )}
            </div>
            <PreviewPanel
              output={outputMeta}
              preview={previewQuery.data ?? null}
              previewCapability={previewCapability}
              loading={previewQuery.isLoading}
              errorMessage={previewErrorMessage}
            />
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">History</h3>
            <span className="text-xs text-muted-foreground">Latest run</span>
          </div>
          <ol className="mt-3 space-y-4 border-l border-border pl-4">
            {historyItems.map((event, index) => (
              <li key={`${event.label}-${index}`} className="relative">
                <span
                  className={clsx(
                    "absolute -left-[9px] top-1.5 h-2.5 w-2.5 rounded-full",
                    historyToneClass(event.tone),
                  )}
                />
                <div className="text-sm font-semibold text-foreground">{event.label}</div>
                <div className="text-xs text-muted-foreground">{event.timestamp}</div>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

function TagEditor({
  workspaceId,
  document,
}: {
  readonly workspaceId: string;
  readonly document: DocumentRecord;
}) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tagList, setTagList] = useState<string[]>(() => document.tags ?? []);

  useEffect(() => {
    const next = document.tags ?? [];
    setTagList(next);
    setDraftValue(next.join(", "));
    setIsEditing(false);
    setErrorMessage(null);
  }, [document.id, (document.tags ?? []).join("|")]);

  const normalizedSavedTags = useMemo(() => normalizeTags(tagList), [tagList]);
  const normalizedDraftTags = useMemo(() => normalizeTags(splitTagInput(draftValue)), [draftValue]);
  const isDirty = !areTagsEqual([...normalizedSavedTags].sort(), [...normalizedDraftTags].sort());
  const tagLimitReached = normalizedDraftTags.length > MAX_DOCUMENT_TAGS;

  const saveTags = useMutation({
    mutationFn: (nextTags: string[]) => replaceDocumentTags(workspaceId, document.id, nextTags),
    onSuccess: (updated) => {
      const next = updated.tags ?? [];
      setTagList(next);
      setDraftValue(next.join(", "));
      setIsEditing(false);
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ["documents-v2", workspaceId] });
    },
    onError: (error) => {
      setErrorMessage(resolveErrorMessage(error, "Unable to update tags."));
    },
  });

  const handleSave = () => {
    if (tagLimitReached) {
      setErrorMessage(`Tag limit reached (${MAX_DOCUMENT_TAGS} max).`);
      return;
    }
    setErrorMessage(null);
    saveTags.mutate(normalizedDraftTags);
  };

  if (!isEditing) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tags</span>
        {tagList.length ? (
          tagList.map((tag) => (
            <span key={tag} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
              {tag}
            </span>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">No tags</span>
        )}
        <button
          type="button"
          className="rounded-full border border-border bg-card px-2.5 py-1 text-xs font-semibold text-muted-foreground"
          onClick={() => setIsEditing(true)}
        >
          Edit tags
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tags</span>
        <span className="text-xs text-muted-foreground">{normalizedDraftTags.length} selected</span>
      </div>
      <Input
        value={draftValue}
        onChange={(event) => setDraftValue(event.target.value)}
        placeholder="Add tags (comma separated)"
        disabled={saveTags.isPending}
        invalid={Boolean(errorMessage)}
      />
      {errorMessage ? <p className="text-xs text-rose-600">{errorMessage}</p> : null}
      {tagLimitReached && !errorMessage ? (
        <p className="text-xs text-amber-600">Tag limit reached ({MAX_DOCUMENT_TAGS} max).</p>
      ) : null}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={handleSave}
          isLoading={saveTags.isPending}
          disabled={!isDirty || saveTags.isPending}
        >
          Save tags
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setDraftValue(tagList.join(", "));
            setIsEditing(false);
            setErrorMessage(null);
          }}
          disabled={saveTags.isPending}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}

function PreviewPanel({
  output,
  preview,
  previewCapability,
  loading,
  errorMessage,
}: {
  readonly output: RunOutput | null;
  readonly preview: OutputPreview | null;
  readonly previewCapability: { kind: "data" | "pdf" | "unsupported"; reason?: string } | null;
  readonly loading: boolean;
  readonly errorMessage: string | null;
}) {
  if (!output || !output.ready) {
    return <p className="mt-3 text-sm text-muted-foreground">Preview will be available once output is generated.</p>;
  }

  if (errorMessage) {
    return <p className="mt-3 text-sm text-rose-600">{errorMessage}</p>;
  }

  if (previewCapability?.kind === "unsupported") {
    return <p className="mt-3 text-sm text-muted-foreground">{previewCapability.reason}</p>;
  }

  if (previewCapability?.kind === "pdf") {
    return (
      <div className="mt-3 flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
        <FileIcon className="h-6 w-6" />
        PDF preview available in full screen.
      </div>
    );
  }

  if (loading) {
    return <p className="mt-3 text-sm text-muted-foreground">Loading preview...</p>;
  }

  if (!preview) {
    return <p className="mt-3 text-sm text-muted-foreground">Preview is not available for this output.</p>;
  }

  if (preview.kind === "json") {
    return (
      <pre className="mt-3 overflow-x-auto rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
        {preview.snippet}
      </pre>
    );
  }

  if (preview.kind === "table") {
    return (
      <div className="mt-3 overflow-hidden rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-background text-muted-foreground">
            <tr>
              {preview.columns.map((column) => (
                <th key={column} className="px-2 py-2 text-left font-semibold">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, rowIndex) => (
              <tr key={`${rowIndex}-${row[0] ?? "row"}`} className="border-t border-border">
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`} className="px-2 py-2 text-muted-foreground">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (preview.kind === "pdf") {
    return (
      <div className="mt-3 flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
        <FileIcon className="h-6 w-6" />
        PDF preview available in full screen.
      </div>
    );
  }

  if (preview.kind === "unsupported") {
    return <p className="mt-3 text-sm text-muted-foreground">{preview.reason}</p>;
  }

  return <p className="mt-3 text-sm text-muted-foreground">Preview is not available for this output.</p>;
}

function historyToneClass(tone: DocumentHistoryItem["tone"]) {
  switch (tone) {
    case "success":
      return "bg-emerald-500";
    case "warning":
      return "bg-amber-400";
    case "error":
      return "bg-rose-500";
    default:
      return "bg-muted";
  }
}

function SelectAllCheckbox({
  checked,
  indeterminate,
  onChange,
}: {
  readonly checked: boolean;
  readonly indeterminate: boolean;
  readonly onChange: () => void;
}) {
  const ref = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className="h-4 w-4 rounded border-border-strong text-foreground"
      aria-label="Select all documents"
    />
  );
}

function RowCheckbox({ checked, onChange }: { readonly checked: boolean; readonly onChange: () => void }) {
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className="h-4 w-4 rounded border-border-strong text-foreground"
      aria-label="Select document"
    />
  );
}

function FileIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path d="M6 3h5l4 4v9a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M11 3v4a1 1 0 0 0 1 1h4" />
    </svg>
  );
}

function InboxIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path d="M4 8h16l-2 10H6L4 8Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 12h8" strokeLinecap="round" />
      <path d="M10 16h4" strokeLinecap="round" />
      <path d="M8 8l2-4h4l2 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" strokeLinecap="round" />
    </svg>
  );
}

function ChevronIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path d="m6 8 4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function buildListQuery(selection: QueueSelection, searchQuery: string): ListDocumentsQuery {
  const selectionQuery = selection.kind === "queue"
    ? QUEUES.find((queue) => queue.id === selection.id)?.query
    : SAVED_VIEWS.find((view) => view.id === selection.id)?.query;

  const query: ListDocumentsQuery = {
    sort: DEFAULT_SORT,
    include_total: true,
    ...(selectionQuery ?? {}),
  };

  if (searchQuery) {
    query.q = searchQuery;
  }

  return query;
}

function isNeedsAttention(document: DocumentRecord) {
  return document.status === "failed" || document.last_run?.status === "failed";
}

function toUiStatus(status: DocumentStatus): UiDocumentStatus {
  switch (status) {
    case "processed":
      return "ready";
    default:
      return status;
  }
}

function formatStatusDetail(document: DocumentRecord, run: RunResource | null) {
  const uiStatus = toUiStatus(document.status);
  const runMessage = run?.failure_message || run?.failure_stage || run?.failure_code || document.last_run?.message;

  switch (uiStatus) {
    case "failed":
      return runMessage ? `Failed - ${runMessage}` : "Failed - needs attention";
    case "processing":
      return runMessage ? `Processing - ${runMessage}` : "Processing - in progress";
    case "ready":
      return "Ready - output available";
    case "uploaded":
      return "Uploaded - queued for processing";
    case "archived":
      return "Archived";
    default:
      return STATUS_META[uiStatus].label;
  }
}

function buildDocumentHistory(document: DocumentRecord, run: RunResource | null): DocumentHistoryItem[] {
  const history: DocumentHistoryItem[] = [];
  const createdLabel = formatRelativeTime(document.created_at);
  history.push({ label: "Uploaded", timestamp: createdLabel, tone: "neutral" });

  if (run) {
    const runStatusLabel = formatRunStatus(run.status);
    if (run.status === "queued") {
      history.push({ label: `Queued (${runStatusLabel})`, timestamp: formatRelativeTime(run.created_at), tone: "warning" });
      return history;
    }
    if (run.status === "running") {
      history.push({ label: "Processing", timestamp: formatRelativeTime(run.started_at ?? run.created_at), tone: "warning" });
      return history;
    }
    if (run.status === "failed") {
      history.push({ label: run.failure_message ? `Failed - ${run.failure_message}` : "Failed", timestamp: formatRelativeTime(run.completed_at ?? run.created_at), tone: "error" });
      return history;
    }
    if (run.status === "succeeded") {
      history.push({ label: "Output ready", timestamp: formatRelativeTime(run.completed_at ?? run.created_at), tone: "success" });
      return history;
    }
  }

  if (document.status === "processing") {
    history.push({ label: "Processing", timestamp: formatRelativeTime(document.updated_at), tone: "warning" });
  }

  return history;
}

function resolveDocumentActivityTime(document: DocumentRecord, run?: RunResource | null) {
  return run?.completed_at ?? run?.started_at ?? document.last_run_at ?? document.updated_at ?? document.created_at;
}

function formatUploaderLabel(document: DocumentRecord) {
  const uploader = document.uploader;
  if (!uploader) return "Unknown uploader";
  return uploader.name || uploader.email || "Unknown uploader";
}

function formatRunStatus(status: RunStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatRelativeTime(value?: string | null) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  const diffMs = date.getTime() - Date.now();
  const diffSeconds = Math.round(diffMs / 1000);
  const absSeconds = Math.abs(diffSeconds);
  if (absSeconds < 60) return relativeTimeFormatter.format(diffSeconds, "second");
  const diffMinutes = Math.round(diffSeconds / 60);
  const absMinutes = Math.abs(diffMinutes);
  if (absMinutes < 60) return relativeTimeFormatter.format(diffMinutes, "minute");
  const diffHours = Math.round(diffMinutes / 60);
  const absHours = Math.abs(diffHours);
  if (absHours < 24) return relativeTimeFormatter.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 30) return relativeTimeFormatter.format(diffDays, "day");
  const diffMonths = Math.round(diffDays / 30);
  if (Math.abs(diffMonths) < 12) return relativeTimeFormatter.format(diffMonths, "month");
  const diffYears = Math.round(diffDays / 365);
  return relativeTimeFormatter.format(diffYears, "year");
}

function formatBytes(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Unknown size";
  }
  if (value === 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const normalized = value / 1024 ** exponent;
  const precision = normalized >= 10 || exponent === 0 ? 0 : 1;
  return `${normalized.toFixed(precision)} ${units[exponent]}`;
}

function resolveOutputFilename(output: RunOutput) {
  if (output.filename) {
    return output.filename;
  }
  if (output.output_path) {
    const segments = output.output_path.split("/");
    return segments[segments.length - 1] || "Processed output";
  }
  return "Processed output";
}

function inferOutputFormat(output: RunOutput): OutputFormat {
  const contentType = output.content_type?.toLowerCase() ?? "";
  if (contentType.includes("json")) return "json";
  if (contentType.includes("csv")) return "csv";
  if (contentType.includes("pdf")) return "pdf";
  if (contentType.includes("spreadsheet") || contentType.includes("excel")) return "xlsx";
  const filename = resolveOutputFilename(output).toLowerCase();
  if (filename.endsWith(".json")) return "json";
  if (filename.endsWith(".csv")) return "csv";
  if (filename.endsWith(".pdf")) return "pdf";
  if (filename.endsWith(".xlsx") || filename.endsWith(".xls")) return "xlsx";
  return "unknown";
}

function formatOutputLabel(format: OutputFormat) {
  switch (format) {
    case "csv":
      return "CSV";
    case "json":
      return "JSON";
    case "pdf":
      return "PDF";
    case "xlsx":
      return "XLSX";
    default:
      return "File";
  }
}

function resolveOutputStatusLabel(
  run: RunResource | null,
  outputReady: boolean,
  outputMeta: RunOutput | null,
) {
  if (outputReady) {
    return "Output ready";
  }
  if (!outputMeta) {
    return "Waiting on output";
  }
  if (run?.status === "failed") {
    return "Output unavailable";
  }
  if (run?.status === "cancelled") {
    return "Output cancelled";
  }
  return "Waiting on output";
}

function resolvePreviewCapability(output: RunOutput) {
  const format = inferOutputFormat(output);
  if (format === "pdf") {
    return { kind: "pdf" } as const;
  }
  if (format !== "csv" && format !== "json") {
    return {
      kind: "unsupported",
      reason: "Preview is not available for this file type yet.",
    } as const;
  }
  if (output.size_bytes && output.size_bytes > MAX_PREVIEW_BYTES) {
    return {
      kind: "unsupported",
      reason: "Preview is disabled for large outputs. Download the file to review it.",
    } as const;
  }
  return { kind: "data" } as const;
}

async function fetchOutputPreview(
  run: RunResource,
  output: RunOutput,
  signal?: AbortSignal,
): Promise<OutputPreview> {
  const format = inferOutputFormat(output);
  if (format !== "csv" && format !== "json") {
    return { kind: "unsupported", reason: "Preview is not available for this file type." };
  }

  const downloadPath =
    output.download_url ?? run.links?.output_download ?? run.links?.output ?? null;
  if (!downloadPath) {
    return { kind: "unsupported", reason: "Output download is unavailable." };
  }

  const response = await fetchOutputText(downloadPath, signal);
  if (!response.ok) {
    throw new Error(`Preview download failed (${response.status}).`);
  }
  const text = await response.text();

  if (format === "json") {
    return { kind: "json", snippet: formatJsonSnippet(text) };
  }

  return parseCsvPreview(text);
}

async function fetchOutputText(downloadPath: string, signal?: AbortSignal) {
  if (downloadPath.startsWith("http")) {
    return fetch(downloadPath, {
      credentials: "include",
      headers: buildApiHeaders("GET"),
      signal,
    });
  }
  return apiFetch(downloadPath, { signal });
}

function parseCsvPreview(text: string): OutputPreview {
  const lines = text.split(/\r?\n/).filter((line) => line.length > 0);
  if (lines.length === 0) {
    return { kind: "unsupported", reason: "Output preview is empty." };
  }

  const headerLine = lines[0] ?? "";
  const delimiter = headerLine.includes("\t") ? "\t" : ",";
  const rows = lines.slice(0, 9).map((line) => parseDelimitedLine(line, delimiter));
  const columns = (rows[0] ?? []).slice(0, 6);
  const previewRows = rows.slice(1, 9).map((row) => row.slice(0, 6));

  return {
    kind: "table",
    columns: columns.length ? columns : ["Column 1"],
    rows: previewRows,
  };
}

function parseDelimitedLine(line: string, delimiter: string) {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === delimiter && !inQuotes) {
      cells.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  cells.push(current.trim());
  return cells;
}

function formatJsonSnippet(text: string) {
  try {
    const parsed = JSON.parse(text);
    return trimPreviewText(JSON.stringify(parsed, null, 2));
  } catch {
    return trimPreviewText(text);
  }
}

function trimPreviewText(text: string) {
  const maxChars = 2000;
  const maxLines = 20;
  const lines = text.split(/\r?\n/);
  const slicedLines = lines.slice(0, maxLines);
  let result = slicedLines.join("\n");
  if (result.length > maxChars) {
    result = `${result.slice(0, maxChars)}...`;
  }
  if (lines.length > maxLines) {
    result = `${result}\n...`;
  }
  return result;
}

function splitTagInput(value: string): string[] {
  return value
    .split(",")
    .map((token) => normalizeTagInput(token))
    .filter(Boolean);
}

function normalizeTagInput(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function normalizeTags(values: readonly string[]) {
  return Array.from(new Set(values.map((value) => normalizeTagInput(value)).filter(Boolean)));
}

function areTagsEqual(left: readonly string[], right: readonly string[]) {
  if (left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return false;
  }
  return true;
}

function resolveErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

async function fetchWorkspaceDocuments(
  workspaceId: string,
  query: ListDocumentsQuery,
  signal?: AbortSignal,
): Promise<DocumentListPage> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document page payload.");
  }

  return data as DocumentListPage;
}

async function fetchDocumentsCount(
  workspaceId: string,
  filters: Partial<ListDocumentsQuery>,
  signal?: AbortSignal,
): Promise<number> {
  const query: ListDocumentsQuery = {
    ...filters,
    page: 1,
    page_size: 1,
    include_total: true,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document count payload.");
  }

  return data.total ?? data.items?.length ?? 0;
}
