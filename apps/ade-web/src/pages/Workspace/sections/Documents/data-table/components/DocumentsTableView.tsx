import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { resolveApiUrl } from "@api/client";
import {
  archiveWorkspaceDocument,
  deleteWorkspaceDocument,
  fetchWorkspaceDocumentRowById,
  patchWorkspaceDocument,
  restoreWorkspaceDocument,
  type DocumentUploadResponse,
  type DocumentRecord,
} from "@api/documents";
import { patchDocumentTags, fetchTagCatalog } from "@api/documents/tags";
import { buildWeakEtag } from "@api/etag";
import { createIdempotencyKey } from "@api/idempotency";
import { Link } from "@app/navigation/Link";
import { listWorkspaceMembers } from "@api/workspaces/api";
import { Button } from "@/components/ui/button";
import type { PresenceParticipant } from "@schema/presence";
import type { UploadManagerItem } from "@hooks/documents/uploadManager";
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
import type { WorkspacePerson, DocumentRow } from "@pages/Workspace/sections/Documents/types";
import { DocumentsPresenceIndicator } from "@pages/Workspace/sections/Documents/components/DocumentsPresenceIndicator";
import { useDocumentsPresence } from "@pages/Workspace/sections/Documents/hooks/useDocumentsPresence";
import { useDocumentsView } from "@pages/Workspace/sections/Documents/hooks/useDocumentsView";

import { DocumentsTable } from "./DocumentsTable";
import { DocumentsEmptyState, DocumentsInlineBanner } from "./DocumentsEmptyState";
import { useDocumentsListParams } from "../hooks/useDocumentsListParams";
import { DEFAULT_DOCUMENT_SORT, normalizeDocumentsFilters, normalizeDocumentsSort } from "../utils";

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

type UploadItem = UploadManagerItem<DocumentUploadResponse>;

type RowMutation = "archive" | "restore" | "delete" | "assign" | "tags";

export function DocumentsTableView({
  workspaceId,
  currentUser,
  configMissing = false,
  processingPaused = false,
  toolbarActions,
  uploadItems,
}: {
  workspaceId: string;
  currentUser: CurrentUser;
  configMissing?: boolean;
  processingPaused?: boolean;
  toolbarActions?: ReactNode;
  uploadItems?: UploadItem[];
}) {
  const { notifyToast } = useNotifications();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentRow | null>(null);
  const [pendingMutations, setPendingMutations] = useState<Record<string, Set<RowMutation>>>({});
  const [archivedFlashIds, setArchivedFlashIds] = useState<Set<string>>(() => new Set());
  const archiveUndoRef = useRef(
    new Map<
      string,
      {
        snapshot: Pick<DocumentRow, "status" | "updatedAt" | "activityAt">;
        undoRequested: boolean;
      }
    >(),
  );
  const archiveFlashTimersRef = useRef<Map<string, number>>(new Map());
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [isAtTop, setIsAtTop] = useState(true);
  const [visibleRange, setVisibleRange] = useState<{ startIndex: number; endIndex: number; total: number } | null>(null);

  const presence = useDocumentsPresence({ workspaceId, enabled: Boolean(workspaceId) });

  const { perPage, sort, filters, joinOperator, q } = useDocumentsListParams();
  const normalizedSort = useMemo(() => normalizeDocumentsSort(sort), [sort]);
  const effectiveSort = useMemo(
    () => normalizedSort ?? DEFAULT_DOCUMENT_SORT,
    [normalizedSort],
  );
  const normalizedFilters = useMemo(() => normalizeDocumentsFilters(filters), [filters]);
  const documentsView = useDocumentsView({
    workspaceId,
    perPage,
    sort: effectiveSort,
    filters: normalizedFilters,
    joinOperator,
    q,
    enabled: Boolean(workspaceId),
    isAtTop,
    visibleStartIndex: visibleRange?.startIndex ?? null,
  });
  const {
    rows: documents,
    documentsById,
    pageCount,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
    fetchNextPage,
    refreshSnapshot,
    updateRow,
    upsertRow,
    removeRow,
    setUploadProgress,
    registerClientRequestId,
    clearClientRequestId,
    queuedChanges,
    applyQueuedChanges,
  } = documentsView;
  const handledUploadsRef = useRef(new Set<string>());
  const completedUploadsRef = useRef(new Set<string>());
  const handleVisibleRangeChange = useCallback(
    (range: { startIndex: number; endIndex: number; total: number }) => {
      setVisibleRange(range);
    },
    [],
  );

  const openDownload = useCallback((url: string) => {
    if (typeof window === "undefined") return;
    const opened = window.open(url, "_blank", "noopener");
    if (!opened) {
      window.location.assign(url);
    }
  }, []);

  const handleDownloadOutput = useCallback(
    (document: DocumentRow) => {
      const runId = document.latestSuccessfulRun?.id ?? null;
      if (!runId) {
        notifyToast({
          title: "Output not available",
          description: "No successful run output exists for this document yet.",
          intent: "warning",
        });
        return;
      }
      const url = resolveApiUrl(`/api/v1/runs/${runId}/output/download`);
      openDownload(url);
    },
    [notifyToast, openDownload],
  );

  const handleDownloadOriginal = useCallback(
    (document: DocumentRow) => {
      const url = resolveApiUrl(
        `/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`,
      );
      openDownload(url);
    },
    [openDownload, workspaceId],
  );

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const handleScroll = () => {
      setIsAtTop(container.scrollTop <= 8);
    };
    handleScroll();
    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, [documents.length, isLoading]);

  useEffect(() => {
    if (!expandedRowId) return;
    if (documentsById[expandedRowId]) return;
    setExpandedRowId(null);
  }, [documentsById, expandedRowId]);

  useEffect(() => {
    if (expandedRowId) {
      setVisibleRange(null);
    }
  }, [expandedRowId]);

  const handleApplyQueuedChanges = useCallback(() => {
    applyQueuedChanges();
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [applyQueuedChanges]);

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

  const createClientRequestId = useCallback(() => createIdempotencyKey("req"), []);

  useEffect(() => {
    if (!uploadItems?.length) return;
    uploadItems.forEach((item) => {
      const documentId =
        item.documentId ?? item.row?.id ?? item.response?.id ?? null;
      if (item.row && !handledUploadsRef.current.has(item.id)) {
        handledUploadsRef.current.add(item.id);
        registerClientRequestId(item.id);
        upsertRow(item.row);
      }

      if (documentId && item.status !== "succeeded" && item.status !== "failed" && item.status !== "cancelled") {
        setUploadProgress(documentId, item.progress.percent ?? 0);
      }

      if (documentId && item.status === "succeeded" && !completedUploadsRef.current.has(item.id)) {
        completedUploadsRef.current.add(item.id);
        setUploadProgress(documentId, null);
        void fetchWorkspaceDocumentRowById(workspaceId, documentId)
          .then((fresh) => {
            upsertRow(fresh);
          })
          .catch(() => null);
      }

      if (
        documentId &&
        (item.status === "failed" || item.status === "cancelled") &&
        !completedUploadsRef.current.has(item.id)
      ) {
        completedUploadsRef.current.add(item.id);
        clearClientRequestId(item.id);
        setUploadProgress(documentId, null);
        removeRow(documentId);
      }
    });
  }, [clearClientRequestId, registerClientRequestId, removeRow, setUploadProgress, upsertRow, uploadItems, workspaceId]);

  const applyDocumentUpdate = useCallback(
    (documentId: string, updated: DocumentRecord) => {
      const activityAt = updated.activityAt ?? updated.updatedAt;
      const etag = updated.etag ?? buildWeakEtag(updated.id, String(updated.version));
      const updates: Partial<DocumentRow> = {
        status: updated.status,
        updatedAt: updated.updatedAt,
        activityAt,
        version: updated.version,
        etag,
        tags: updated.tags,
        assignee: updated.assignee ?? null,
        uploader: updated.uploader ?? null,
        latestRun: updated.latestRun ?? null,
        latestSuccessfulRun: updated.latestSuccessfulRun ?? null,
        latestResult: updated.latestResult ?? null,
      };
      updateRow(documentId, updates);
    },
    [updateRow],
  );

  const markRowPending = useCallback((documentId: string, action: RowMutation) => {
    setPendingMutations((current) => {
      const next = new Set(current[documentId] ?? []);
      next.add(action);
      return { ...current, [documentId]: next };
    });
  }, []);

  const clearRowPending = useCallback((documentId: string, action?: RowMutation) => {
    setPendingMutations((current) => {
      const existing = current[documentId];
      if (!existing) return current;
      if (!action) {
        const next = { ...current };
        delete next[documentId];
        return next;
      }
      const nextSet = new Set(existing);
      nextSet.delete(action);
      if (nextSet.size === 0) {
        const next = { ...current };
        delete next[documentId];
        return next;
      }
      return { ...current, [documentId]: nextSet };
    });
  }, []);

  const isRowMutationPending = useCallback(
    (documentId: string) => (pendingMutations[documentId]?.size ?? 0) > 0,
    [pendingMutations],
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
    async (documentId: string, options: { silent?: boolean; ifMatch?: string | null } = {}) => {
      const current = documentsById[documentId];
      if (!current) {
        notifyToast({
          title: "Unable to restore document",
          description: "Document not found in the current list.",
          intent: "danger",
        });
        return;
      }
      const ifMatch =
        options.ifMatch ?? current.etag ?? buildWeakEtag(documentId, String(current.version));
      const requestId = createClientRequestId();
      registerClientRequestId(requestId);
      markRowPending(documentId, "restore");
      try {
        const updated = await restoreWorkspaceDocument(workspaceId, documentId, {
          clientRequestId: requestId,
          ifMatch,
        });
        applyDocumentUpdate(documentId, updated);
        if (!options.silent) {
          notifyToast({ title: "Document restored.", intent: "success", duration: 4000 });
        }
      } catch (error) {
        clearClientRequestId(requestId);
        notifyToast({
          title: error instanceof Error ? error.message : "Unable to restore document.",
          intent: "danger",
        });
      } finally {
        clearRowPending(documentId, "restore");
      }
    },
    [
      applyDocumentUpdate,
      clearClientRequestId,
      clearRowPending,
      createClientRequestId,
      documentsById,
      markRowPending,
      notifyToast,
      registerClientRequestId,
      workspaceId,
    ],
  );

  const onAssign = useCallback(
    async (documentId: string, assigneeKey: string | null) => {
      const current = documentsById[documentId];
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
      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      const optimisticAssignee = assigneeId
        ? { id: assigneeId, name: assigneeLabel, email: assigneeEmail }
        : null;
      const snapshot = current.assignee ?? null;

      const requestId = createClientRequestId();
      registerClientRequestId(requestId);
      markRowPending(documentId, "assign");
      updateRow(documentId, { assignee: optimisticAssignee });
      try {
        const updated = await patchWorkspaceDocument(
          workspaceId,
          documentId,
          { assigneeId },
          { ifMatch, clientRequestId: requestId },
        );
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
        clearClientRequestId(requestId);
        updateRow(documentId, { assignee: snapshot });
        notifyToast({
          title: "Unable to update assignee",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      } finally {
        clearRowPending(documentId, "assign");
      }
    },
    [
      applyDocumentUpdate,
      clearClientRequestId,
      clearRowPending,
      createClientRequestId,
      documentsById,
      markRowPending,
      notifyToast,
      people,
      registerClientRequestId,
      updateRow,
      workspaceId,
    ],
  );

  const onToggleTag = useCallback(
    async (documentId: string, tag: string) => {
      const current = documentsById[documentId];
      if (!current) return;
      const tags = current.tags ?? [];
      const hasTag = tags.includes(tag);
      const nextTags = hasTag ? tags.filter((t) => t !== tag) : [...tags, tag];

      const requestId = createClientRequestId();
      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      registerClientRequestId(requestId);
      markRowPending(documentId, "tags");
      updateRow(documentId, { tags: nextTags });
      try {
        const updated = await patchDocumentTags(
          workspaceId,
          documentId,
          hasTag ? { remove: [tag] } : { add: [tag] },
          undefined,
          { clientRequestId: requestId, ifMatch },
        );
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
        clearClientRequestId(requestId);
        updateRow(documentId, { tags });
        notifyToast({
          title: "Unable to update tags",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      } finally {
        clearRowPending(documentId, "tags");
      }
    },
    [
      applyDocumentUpdate,
      clearClientRequestId,
      clearRowPending,
      createClientRequestId,
      documentsById,
      markRowPending,
      notifyToast,
      registerClientRequestId,
      updateRow,
      workspaceId,
    ],
  );

  const onArchive = useCallback(
    async (documentId: string) => {
      const current = documentsById[documentId];
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
      updateRow(documentId, {
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
                updateRow(documentId, entry.snapshot);
                clearArchivedFlash(documentId);
                return;
              }
              void restoreDocument(documentId, { silent: true });
            },
          },
        ],
      });

      const requestId = createClientRequestId();
      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      registerClientRequestId(requestId);
      markRowPending(documentId, "archive");
      try {
        const updated = await archiveWorkspaceDocument(workspaceId, documentId, {
          clientRequestId: requestId,
          ifMatch,
        });
        const entry = archiveUndoRef.current.get(documentId);
        if (entry?.undoRequested) {
          const undoMatch =
            updated.etag ?? buildWeakEtag(updated.id, String(updated.version));
          await restoreDocument(documentId, { silent: true, ifMatch: undoMatch });
          return;
        }
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
        clearClientRequestId(requestId);
        const entry = archiveUndoRef.current.get(documentId);
        if (entry) {
          updateRow(documentId, entry.snapshot);
          clearArchivedFlash(documentId);
        }
        notifyToast({
          title: error instanceof Error ? error.message : "Unable to archive document.",
          intent: "danger",
        });
      } finally {
        archiveUndoRef.current.delete(documentId);
        clearRowPending(documentId, "archive");
      }
    },
    [
      applyDocumentUpdate,
      clearClientRequestId,
      clearRowPending,
      clearArchivedFlash,
      createClientRequestId,
      documentsById,
      markRowPending,
      notifyToast,
      registerClientRequestId,
      restoreDocument,
      triggerArchivedFlash,
      updateRow,
      workspaceId,
    ],
  );

  const onRestore = useCallback(
    async (documentId: string) => {
      await restoreDocument(documentId);
    },
    [restoreDocument],
  );

  const onDeleteRequest = useCallback((document: DocumentRow) => {
    setDeleteTarget(document);
  }, []);

  const onDeleteCancel = useCallback(() => {
    setDeleteTarget(null);
  }, []);

  const onDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    const ifMatch = deleteTarget.etag ?? buildWeakEtag(deleteTarget.id, String(deleteTarget.version));
    const requestId = createClientRequestId();
    registerClientRequestId(requestId);
    markRowPending(deleteTarget.id, "delete");
    try {
      await deleteWorkspaceDocument(workspaceId, deleteTarget.id, {
        ifMatch,
        clientRequestId: requestId,
      });
      removeRow(deleteTarget.id);
      notifyToast({ title: "Document deleted.", intent: "success", duration: 4000 });
      setDeleteTarget(null);
    } catch (error) {
      clearClientRequestId(requestId);
      notifyToast({
        title: error instanceof Error ? error.message : "Unable to delete document.",
        intent: "danger",
      });
    } finally {
      clearRowPending(deleteTarget.id, "delete");
    }
  }, [
    clearClientRequestId,
    clearRowPending,
    createClientRequestId,
    deleteTarget,
    markRowPending,
    notifyToast,
    registerClientRequestId,
    removeRow,
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

  if (isLoading) {
    return (
      <div className="min-h-[240px]">
        <DocumentsEmptyState
          title="Loading documents"
          description="Fetching the latest processing activity."
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[240px]">
        <DocumentsEmptyState
          title="Unable to load documents"
          description="We could not refresh this view. Try again."
          action={{ label: "Try again", onClick: () => refreshSnapshot() }}
        />
      </div>
    );
  }

  const configBuilderPath = `/workspaces/${workspaceId}/config-builder`;
  const processingSettingsPath = `/workspaces/${workspaceId}/settings/processing`;
  const deletePending =
    deleteTarget ? pendingMutations[deleteTarget.id]?.has("delete") ?? false : false;
  const queuedCount = queuedChanges.length;
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
          className="border-amber-200 bg-amber-50/60 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
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
          className="border-amber-200 bg-amber-50/60 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={processingSettingsPath}>Open processing settings</Link>
            </Button>
          }
        />
      ) : null}
      {queuedCount > 0 && !isAtTop ? (
        <DocumentsInlineBanner
          title={`${queuedCount} new update${queuedCount === 1 ? "" : "s"} available`}
          description="Scroll to the top or apply updates to refresh the list."
          actions={
            <Button size="sm" variant="outline" onClick={handleApplyQueuedChanges}>
              Show updates
            </Button>
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
        onDownloadOutput={handleDownloadOutput}
        onDownloadOriginal={handleDownloadOriginal}
        expandedRowId={expandedRowId}
        onTogglePreview={handleTogglePreview}
        isRowActionPending={isRowMutationPending}
        archivedFlashIds={archivedFlashIds}
        toolbarActions={toolbarContent}
        scrollContainerRef={scrollContainerRef}
        onVisibleRangeChange={handleVisibleRangeChange}
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
