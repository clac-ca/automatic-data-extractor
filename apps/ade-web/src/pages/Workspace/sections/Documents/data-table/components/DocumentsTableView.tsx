import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  archiveWorkspaceDocument,
  deleteWorkspaceDocument,
  fetchWorkspaceDocuments,
  patchWorkspaceDocument,
  restoreWorkspaceDocument,
  type DocumentPageResult,
  type DocumentRecord,
} from "@api/documents";
import { documentChangesStreamUrl, streamDocumentChanges } from "@api/documents/changes";
import { patchDocumentTags, fetchTagCatalog } from "@api/documents/tags";
import { ApiError } from "@api/errors";
import { buildWeakEtag } from "@api/etag";
import { Link } from "@app/navigation/Link";
import { listWorkspaceMembers } from "@api/workspaces/api";
import { Button } from "@/components/ui/button";
import type { PresenceParticipant } from "@schema/presence";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useNotifications } from "@components/providers/notifications";
import { shortId } from "@pages/Workspace/sections/Documents/utils";
import { mergeDocumentChangeIntoPages } from "@pages/Workspace/sections/Documents/changeFeed";
import type { WorkspacePerson } from "@pages/Workspace/sections/Documents/types";
import { DocumentsPresenceIndicator } from "@pages/Workspace/sections/Documents/components/DocumentsPresenceIndicator";
import { useDocumentsPresence } from "@pages/Workspace/sections/Documents/hooks/useDocumentsPresence";

import { DocumentsTable } from "./DocumentsTable";
import { DocumentsEmptyState, DocumentsInlineBanner } from "./DocumentsEmptyState";
import { useDocumentsListParams } from "../hooks/useDocumentsListParams";
import type { DocumentChangeEntry, DocumentListRow } from "../types";
import { normalizeDocumentsFilters, normalizeDocumentsSort } from "../utils";

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

function sleep(duration: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    let timeout: number;
    const onAbort = () => {
      window.clearTimeout(timeout);
      signal.removeEventListener("abort", onAbort);
      resolve();
    };
    timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, duration);
    signal.addEventListener("abort", onAbort);
  });
}

export function DocumentsTableView({
  workspaceId,
  currentUser,
  configMissing = false,
  processingPaused = false,
  toolbarActions,
}: {
  workspaceId: string;
  currentUser: CurrentUser;
  configMissing?: boolean;
  processingPaused?: boolean;
  toolbarActions?: ReactNode;
}) {
  const queryClient = useQueryClient();
  const { notifyToast } = useNotifications();
  const [updatesAvailable, setUpdatesAvailable] = useState(false);
  const lastCursorRef = useRef<string | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentListRow | null>(null);
  const [pendingActions, setPendingActions] = useState<Record<string, "archive" | "restore" | "delete">>({});
  const [archivedFlashIds, setArchivedFlashIds] = useState<Set<string>>(() => new Set());
  const archiveUndoRef = useRef(
    new Map<
      string,
      {
        snapshot: Pick<DocumentListRow, "status" | "updatedAt" | "activityAt">;
        undoRequested: boolean;
      }
    >(),
  );
  const archiveFlashTimersRef = useRef<Map<string, number>>(new Map());
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  const presence = useDocumentsPresence({ workspaceId, enabled: Boolean(workspaceId) });

  const { perPage, sort, filters, joinOperator, q } = useDocumentsListParams();
  const normalizedSort = useMemo(() => normalizeDocumentsSort(sort), [sort]);
  const normalizedFilters = useMemo(() => normalizeDocumentsFilters(filters), [filters]);
  const sortTokens = useMemo(
    () =>
      normalizedSort
        ? normalizedSort.split(",").map((token) => token.trim()).filter(Boolean)
        : [],
    [normalizedSort],
  );
  const filtersKey = useMemo(
    () => (normalizedFilters.length > 0 ? JSON.stringify(normalizedFilters) : ""),
    [normalizedFilters],
  );
  const queryKey = useMemo(
    () => [
      "documents",
      workspaceId,
      perPage,
      normalizedSort,
      filtersKey,
      joinOperator,
      q,
    ],
    [workspaceId, perPage, normalizedSort, filtersKey, joinOperator, q],
  );

  const documentsQuery = useInfiniteQuery<DocumentPageResult>({
    queryKey,
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          page: typeof pageParam === "number" ? pageParam : 1,
          perPage,
          sort: normalizedSort,
          filters: normalizedFilters.length > 0 ? normalizedFilters : undefined,
          joinOperator: joinOperator ?? undefined,
          q: q ?? undefined,
        },
        signal,
      ),
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pageCount ? lastPage.page + 1 : undefined,
    enabled: Boolean(workspaceId),
    staleTime: 15_000,
  });
  const {
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch: refetchDocuments,
  } = documentsQuery;

  const documents = useMemo(
    () => documentsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [documentsQuery.data?.pages],
  );
  const documentsById = useMemo(
    () => new Map(documents.map((doc) => [doc.id, doc])),
    [documents],
  );

  useEffect(() => {
    if (!expandedRowId) return;
    if (documentsById.has(expandedRowId)) return;
    setExpandedRowId(null);
  }, [documentsById, expandedRowId]);

  const toolbarParticipants = useMemo(
    () => dedupeParticipants(presence.participants, presence.clientId),
    [presence.clientId, presence.participants],
  );

  const rowPresence = useMemo(
    () => mapPresenceByDocument(presence.participants, presence.clientId),
    [presence.clientId, presence.participants],
  );

  const handleTogglePreview = useCallback((documentId: string) => {
    setExpandedRowId((current) => (current === documentId ? null : documentId));
  }, []);

  useEffect(() => {
    if (presence.connectionState !== "open") return;
    const selection = expandedRowId
      ? { documentId: expandedRowId, mode: "preview" }
      : { documentId: null };
    presence.sendSelection(selection);
  }, [expandedRowId, presence.connectionState, presence.sendSelection]);

  const membersQuery = useQuery({
    queryKey: ["documents-members", workspaceId],
    queryFn: ({ signal }) =>
      listWorkspaceMembers(workspaceId, { page: 1, pageSize: 200, signal }),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const people = useMemo<WorkspacePerson[]>(() => {
    const set = new Map<string, WorkspacePerson>();
    const currentUserKey = `user:${currentUser.id}`;
    set.set(currentUserKey, {
      key: currentUserKey,
      label: currentUser.label,
      kind: "user",
      userId: currentUser.id,
    });

    const members = membersQuery.data?.items ?? [];
    members.forEach((member) => {
      const key = `user:${member.user_id}`;
      const label =
        member.user_id === currentUser.id
          ? currentUser.label
          : `Member ${shortId(member.user_id)}`;
      if (!set.has(key)) {
        set.set(key, { key, label, kind: "user", userId: member.user_id });
      }
    });

    return Array.from(set.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [currentUser.id, currentUser.label, membersQuery.data?.items]);

  const tagsQuery = useQuery({
    queryKey: ["documents-tags", workspaceId],
    queryFn: ({ signal }) =>
      fetchTagCatalog(
        workspaceId,
        { page: 1, perPage: 200, sort: "-count" },
        signal,
      ),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const tagOptions = useMemo(
    () => tagsQuery.data?.items?.map((item) => item.tag) ?? [],
    [tagsQuery.data?.items],
  );

  const updateDocumentRow = useCallback(
    (documentId: string, updates: Partial<DocumentPageResult["items"][number]>) => {
      queryClient.setQueryData(queryKey, (existing: typeof documentsQuery.data | undefined) => {
        if (!existing?.pages) return existing;
        return {
          ...existing,
          pages: existing.pages.map((page) => ({
            ...page,
            items: (page.items ?? []).map((item) =>
              item.id === documentId ? { ...item, ...updates } : item,
            ),
          })),
        };
      });
    },
    [queryClient, queryKey, documentsQuery.data],
  );

  const removeDocumentRow = useCallback(
    (documentId: string) => {
      queryClient.setQueryData(queryKey, (existing: typeof documentsQuery.data | undefined) => {
        if (!existing?.pages) return existing;
        return {
          ...existing,
          pages: existing.pages.map((page) => ({
            ...page,
            items: (page.items ?? []).filter((item) => item.id !== documentId),
          })),
        };
      });
    },
    [queryClient, queryKey, documentsQuery.data],
  );

  const applyDocumentUpdate = useCallback(
    (documentId: string, updated: DocumentRecord) => {
      const updates: Partial<DocumentPageResult["items"][number]> = {
        status: updated.status,
        updatedAt: updated.updatedAt,
      };
      const activityAt = updated.activityAt ?? updated.updatedAt;
      if (activityAt) {
        updates.activityAt = activityAt;
      }
      if (updated.etag !== undefined) {
        updates.etag = updated.etag ?? null;
      }
      if (updated.tags !== undefined) {
        updates.tags = updated.tags;
      }
      if (updated.assignee !== undefined) {
        updates.assignee = updated.assignee ?? null;
      }
      if (updated.uploader !== undefined) {
        updates.uploader = updated.uploader ?? null;
      }
      if (updated.latestRun !== undefined) {
        updates.latestRun = updated.latestRun ?? null;
      }
      if (updated.latestSuccessfulRun !== undefined) {
        updates.latestSuccessfulRun = updated.latestSuccessfulRun ?? null;
      }
      if (updated.latestResult !== undefined) {
        updates.latestResult = updated.latestResult ?? null;
      }
      updateDocumentRow(documentId, updates);
    },
    [updateDocumentRow],
  );

  const markActionPending = useCallback((documentId: string, action: "archive" | "restore" | "delete") => {
    setPendingActions((current) => ({ ...current, [documentId]: action }));
  }, []);

  const clearActionPending = useCallback((documentId: string) => {
    setPendingActions((current) => {
      if (!current[documentId]) return current;
      const next = { ...current };
      delete next[documentId];
      return next;
    });
  }, []);

  const isRowActionPending = useCallback(
    (documentId: string) => Boolean(pendingActions[documentId]),
    [pendingActions],
  );

  const triggerArchivedFlash = useCallback((documentId: string) => {
    setArchivedFlashIds((current) => {
      if (current.has(documentId)) return current;
      const next = new Set(current);
      next.add(documentId);
      return next;
    });

    if (typeof window === "undefined") return;
    const existing = archiveFlashTimersRef.current.get(documentId);
    if (existing) {
      window.clearTimeout(existing);
    }
    const timeoutId = window.setTimeout(() => {
      archiveFlashTimersRef.current.delete(documentId);
      setArchivedFlashIds((current) => {
        if (!current.has(documentId)) return current;
        const next = new Set(current);
        next.delete(documentId);
        return next;
      });
    }, 1600);
    archiveFlashTimersRef.current.set(documentId, timeoutId);
  }, []);

  const clearArchivedFlash = useCallback((documentId: string) => {
    setArchivedFlashIds((current) => {
      if (!current.has(documentId)) return current;
      const next = new Set(current);
      next.delete(documentId);
      return next;
    });
    const existing = archiveFlashTimersRef.current.get(documentId);
    if (existing && typeof window !== "undefined") {
      window.clearTimeout(existing);
      archiveFlashTimersRef.current.delete(documentId);
    }
  }, []);

  const restoreDocument = useCallback(
    async (documentId: string, options: { silent?: boolean } = {}) => {
      markActionPending(documentId, "restore");
      try {
        const updated = await restoreWorkspaceDocument(workspaceId, documentId);
        applyDocumentUpdate(documentId, updated);
        if (!options.silent) {
          notifyToast({ title: "Document restored.", intent: "success", duration: 4000 });
        }
      } catch (error) {
        notifyToast({
          title: error instanceof Error ? error.message : "Unable to restore document.",
          intent: "danger",
        });
      } finally {
        clearActionPending(documentId);
      }
    },
    [applyDocumentUpdate, clearActionPending, markActionPending, notifyToast, workspaceId],
  );

  const onAssign = useCallback(
    async (documentId: string, assigneeKey: string | null) => {
      const current = documentsById.get(documentId);
      if (!current) {
        notifyToast({
          title: "Unable to update assignee",
          description: "Document not found in the current list.",
          intent: "danger",
        });
        return;
      }
      const assigneeId = assigneeKey?.startsWith("user:") ? assigneeKey.slice(5) : null;
      const assigneeLabel = assigneeKey
        ? people.find((person) => person.key === assigneeKey)?.label ?? assigneeKey
        : null;
      const assigneeEmail = assigneeLabel && assigneeLabel.includes("@") ? assigneeLabel : "";
      const ifMatch = current.etag ?? buildWeakEtag(documentId, current.updatedAt);

      try {
        const updated = await patchWorkspaceDocument(
          workspaceId,
          documentId,
          { assigneeId },
          { ifMatch },
        );
        applyDocumentUpdate(documentId, updated);
        if (!updated.assignee && assigneeId) {
          updateDocumentRow(documentId, {
            assignee: { id: assigneeId, name: assigneeLabel, email: assigneeEmail },
          });
        }
      } catch (error) {
        notifyToast({
          title: "Unable to update assignee",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      }
    },
    [applyDocumentUpdate, documentsById, notifyToast, people, updateDocumentRow, workspaceId],
  );

  const onToggleTag = useCallback(
    async (documentId: string, tag: string) => {
      const current = documentsById.get(documentId);
      if (!current) return;
      const tags = current.tags ?? [];
      const hasTag = tags.includes(tag);
      try {
        await patchDocumentTags(workspaceId, documentId, hasTag ? { remove: [tag] } : { add: [tag] });
        const nextTags = hasTag ? tags.filter((t) => t !== tag) : [...tags, tag];
        updateDocumentRow(documentId, { tags: nextTags });
      } catch (error) {
        notifyToast({
          title: "Unable to update tags",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      }
    },
    [documentsById, notifyToast, updateDocumentRow, workspaceId],
  );

  const onArchive = useCallback(
    async (documentId: string) => {
      const current = documentsById.get(documentId);
      if (!current) {
        return;
      }

      const snapshot = {
        status: current.status,
        updatedAt: current.updatedAt,
        activityAt: current.activityAt,
      };
      archiveUndoRef.current.set(documentId, { snapshot, undoRequested: false });

      const now = new Date().toISOString();
      updateDocumentRow(documentId, {
        status: "archived",
        updatedAt: now,
        activityAt: now,
      });
      triggerArchivedFlash(documentId);

      notifyToast({
        title: "Document archived.",
        intent: "success",
        duration: 6000,
        actions: [
          {
            label: "Undo",
            variant: "ghost",
            onSelect: () => {
              const entry = archiveUndoRef.current.get(documentId);
              if (entry) {
                entry.undoRequested = true;
                updateDocumentRow(documentId, entry.snapshot);
                clearArchivedFlash(documentId);
                return;
              }
              void restoreDocument(documentId, { silent: true });
            },
          },
        ],
      });

      markActionPending(documentId, "archive");
      try {
        const updated = await archiveWorkspaceDocument(workspaceId, documentId);
        const entry = archiveUndoRef.current.get(documentId);
        if (entry?.undoRequested) {
          await restoreDocument(documentId, { silent: true });
          return;
        }
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
        const entry = archiveUndoRef.current.get(documentId);
        if (entry) {
          updateDocumentRow(documentId, entry.snapshot);
          clearArchivedFlash(documentId);
        }
        notifyToast({
          title: error instanceof Error ? error.message : "Unable to archive document.",
          intent: "danger",
        });
      } finally {
        archiveUndoRef.current.delete(documentId);
        clearActionPending(documentId);
      }
    },
    [
      applyDocumentUpdate,
      clearActionPending,
      clearArchivedFlash,
      documentsById,
      markActionPending,
      notifyToast,
      restoreDocument,
      triggerArchivedFlash,
      updateDocumentRow,
      workspaceId,
    ],
  );

  const onRestore = useCallback(
    async (documentId: string) => {
      await restoreDocument(documentId);
    },
    [restoreDocument],
  );

  const onDeleteRequest = useCallback((document: DocumentListRow) => {
    setDeleteTarget(document);
  }, []);

  const onDeleteCancel = useCallback(() => {
    setDeleteTarget(null);
  }, []);

  const onDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    markActionPending(deleteTarget.id, "delete");
    try {
      await deleteWorkspaceDocument(workspaceId, deleteTarget.id);
      removeDocumentRow(deleteTarget.id);
      notifyToast({ title: "Document deleted.", intent: "success", duration: 4000 });
      setDeleteTarget(null);
    } catch (error) {
      notifyToast({
        title: error instanceof Error ? error.message : "Unable to delete document.",
        intent: "danger",
      });
    } finally {
      clearActionPending(deleteTarget.id);
    }
  }, [
    clearActionPending,
    deleteTarget,
    markActionPending,
    notifyToast,
    removeDocumentRow,
    workspaceId,
  ]);

  const changesCursor =
    documentsQuery.data?.pages[0]?.changesCursor ??
    documentsQuery.data?.pages[0]?.changesCursorHeader ??
    null;

  const applyChange = useCallback(
    (change: DocumentChangeEntry) => {
      let shouldPrompt = Boolean(change.requiresRefresh);

      queryClient.setQueryData(queryKey, (existing: typeof documentsQuery.data | undefined) => {
        if (!existing) {
          return existing;
        }
        const result = mergeDocumentChangeIntoPages(existing, change, { sortTokens });
        shouldPrompt = shouldPrompt || result.updatesAvailable;
        return result.data;
      });

      if (shouldPrompt) {
        setUpdatesAvailable((current) => current || true);
      }
    },
    [queryClient, queryKey, sortTokens],
  );

  useEffect(() => {
    setUpdatesAvailable(false);
    lastCursorRef.current = changesCursor;
  }, [changesCursor, filtersKey, joinOperator, perPage, q, normalizedSort, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !changesCursor) return;

    const controller = new AbortController();
    let retryAttempt = 0;

    const streamChanges = async () => {
      while (!controller.signal.aborted) {
        const cursor = lastCursorRef.current ?? changesCursor;
        const streamUrl = documentChangesStreamUrl(workspaceId, {
          cursor,
          sort: normalizedSort ?? undefined,
          filters: normalizedFilters.length > 0 ? normalizedFilters : undefined,
          joinOperator: joinOperator ?? undefined,
          q: q ?? undefined,
        });

        try {
          for await (const change of streamDocumentChanges(streamUrl, controller.signal)) {
            lastCursorRef.current = change.cursor;
            applyChange(change);
            retryAttempt = 0;
          }
        } catch (error) {
          if (controller.signal.aborted) return;

          if (error instanceof ApiError && error.status === 410) {
            setUpdatesAvailable(false);
            void refetchDocuments();
            return;
          }

          console.warn("Documents change stream failed", error);
        }

        if (controller.signal.aborted) return;

        const baseDelay = 1000;
        const maxDelay = 30000;
        const delay = Math.min(maxDelay, baseDelay * 2 ** Math.min(retryAttempt, 5));
        retryAttempt += 1;
        const jitter = Math.floor(delay * 0.15 * Math.random());
        await sleep(delay + jitter, controller.signal);
      }
    };

    void streamChanges();

    return () => controller.abort();
  }, [
    applyChange,
    changesCursor,
    joinOperator,
    normalizedFilters,
    normalizedSort,
    q,
    refetchDocuments,
    workspaceId,
  ]);

  useEffect(() => {
    if (!loadMoreRef.current) return;
    if (!hasNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        if (isFetchingNextPage) return;
        void fetchNextPage();
      },
      {
        root: scrollContainerRef.current,
        rootMargin: "200px",
      },
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  if (documentsQuery.isLoading) {
    return (
      <div className="min-h-[240px]">
        <DocumentsEmptyState
          title="Loading documents"
          description="Fetching the latest processing activity."
        />
      </div>
    );
  }

  if (documentsQuery.isError) {
    return (
      <div className="min-h-[240px]">
        <DocumentsEmptyState
          title="Unable to load documents"
          description="We could not refresh this view. Try again."
          action={{ label: "Try again", onClick: () => documentsQuery.refetch() }}
        />
      </div>
    );
  }

  const pageCount = documentsQuery.data?.pages[0]?.pageCount ?? 1;
  const handleRefresh = () => {
    setUpdatesAvailable(false);
    void documentsQuery.refetch();
  };

  const configBuilderPath = `/workspaces/${workspaceId}/config-builder`;
  const processingSettingsPath = `/workspaces/${workspaceId}/settings/processing`;
  const deletePending =
    deleteTarget ? pendingActions[deleteTarget.id] === "delete" : false;
  const toolbarPresence = (
    <DocumentsPresenceIndicator
      participants={toolbarParticipants}
      connectionState={presence.connectionState}
    />
  );
  const toolbarContent = toolbarActions ? (
    <div className="flex flex-wrap items-center gap-3">
      {toolbarPresence}
      {toolbarActions}
    </div>
  ) : (
    toolbarPresence
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
      {configMissing ? (
        <DocumentsInlineBanner
          title="No active configuration"
          description="Uploads will be stored, but runs won't start until you activate a configuration."
          className="border-warning-200 bg-warning-50/60 text-warning-900 dark:border-warning-500/40 dark:bg-warning-500/10 dark:text-warning-100"
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={configBuilderPath}>Open config builder</Link>
            </Button>
          }
        />
      ) : null}
      {processingPaused ? (
        <DocumentsInlineBanner
          title="Processing paused"
          description="Uploads are queued and won't start until processing is resumed."
          className="border-warning-200 bg-warning-50/60 text-warning-900 dark:border-warning-500/40 dark:bg-warning-500/10 dark:text-warning-100"
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={processingSettingsPath}>Open processing settings</Link>
            </Button>
          }
        />
      ) : null}
      {updatesAvailable ? (
        <DocumentsInlineBanner
          title="Updates available"
          description="Refresh to load the latest changes."
          actions={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={documentsQuery.isFetching}
              >
                {documentsQuery.isFetching ? "Refreshing..." : "Refresh"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setUpdatesAvailable(false)}>
                Dismiss
              </Button>
            </>
          }
        />
      ) : null}
      <DocumentsTable
        data={documents}
        pageCount={pageCount}
        workspaceId={workspaceId}
        people={people}
        tagOptions={tagOptions}
        rowPresence={rowPresence}
        onAssign={onAssign}
        onToggleTag={onToggleTag}
        onArchive={onArchive}
        onRestore={onRestore}
        onDeleteRequest={onDeleteRequest}
        expandedRowId={expandedRowId}
        onTogglePreview={handleTogglePreview}
        isRowActionPending={isRowActionPending}
        archivedFlashIds={archivedFlashIds}
        toolbarActions={toolbarContent}
        scrollContainerRef={scrollContainerRef}
        scrollFooter={
          <>
            {hasNextPage ? (
              <div className="flex w-full items-center justify-center py-2 text-xs text-muted-foreground">
                {isFetchingNextPage ? "Loading more documents..." : "Scroll to load more"}
              </div>
            ) : null}
            <div ref={loadMoreRef} className="h-1 w-full" />
          </>
        }
      />
      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => (!open ? onDeleteCancel() : undefined)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete document?</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `This permanently deletes “${deleteTarget.name}”. This action cannot be undone.`
                : "This permanently deletes the document. This action cannot be undone."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={onDeleteCancel} disabled={deletePending}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={onDeleteConfirm} disabled={deletePending}>
              {deletePending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function getParticipantLabel(participant: PresenceParticipant) {
  return participant.display_name || participant.email || "Workspace member";
}

function getSelectedDocumentId(participant: PresenceParticipant) {
  const selection = participant.selection;
  if (!selection || typeof selection !== "object") return null;
  const documentId = selection["documentId"];
  return typeof documentId === "string" ? documentId : null;
}

function rankParticipant(participant: PresenceParticipant) {
  let score = 0;
  if (participant.status === "active") score += 2;
  if (getSelectedDocumentId(participant)) score += 3;
  if (participant.editing) score += 1;
  return score;
}

function sortParticipants(participants: PresenceParticipant[]) {
  return participants.sort((a, b) => {
    const aPriority = a.status === "active" ? 0 : 1;
    const bPriority = b.status === "active" ? 0 : 1;
    if (aPriority !== bPriority) return aPriority - bPriority;
    const aLabel = getParticipantLabel(a).toLowerCase();
    const bLabel = getParticipantLabel(b).toLowerCase();
    return aLabel.localeCompare(bLabel);
  });
}

function dedupeParticipants(participants: PresenceParticipant[], clientId: string | null) {
  const byUser = new Map<string, PresenceParticipant>();
  for (const participant of participants) {
    if (participant.client_id === clientId) continue;
    const key = participant.user_id || participant.client_id;
    const existing = byUser.get(key);
    if (!existing) {
      byUser.set(key, participant);
      continue;
    }
    if (rankParticipant(participant) > rankParticipant(existing)) {
      byUser.set(key, participant);
    }
  }
  return sortParticipants(Array.from(byUser.values()));
}

function mapPresenceByDocument(participants: PresenceParticipant[], clientId: string | null) {
  const map = new Map<string, Map<string, PresenceParticipant>>();
  participants.forEach((participant) => {
    if (participant.client_id === clientId) return;
    const documentId = getSelectedDocumentId(participant);
    if (!documentId) return;
    const userKey = participant.user_id || participant.client_id;
    const bucket = map.get(documentId) ?? new Map<string, PresenceParticipant>();
    const existing = bucket.get(userKey);
    if (!existing || rankParticipant(participant) > rankParticipant(existing)) {
      bucket.set(userKey, participant);
    }
    map.set(documentId, bucket);
  });

  const resolved = new Map<string, PresenceParticipant[]>();
  map.forEach((bucket, documentId) => {
    resolved.set(documentId, sortParticipants(Array.from(bucket.values())));
  });
  return resolved;
}
