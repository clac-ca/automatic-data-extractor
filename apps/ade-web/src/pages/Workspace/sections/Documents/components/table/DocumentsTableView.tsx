import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { resolveApiUrl } from "@api/client";
import {
  archiveWorkspaceDocument,
  deleteWorkspaceDocument,
  DocumentChangesResyncError,
  fetchWorkspaceDocumentChanges,
  fetchWorkspaceDocumentRowById,
  patchWorkspaceDocument,
  restoreWorkspaceDocument,
  type DocumentChangeEntry,
  type DocumentListRow,
  type DocumentRecord,
  type DocumentUploadResponse,
} from "@api/documents";
import { patchDocumentTags, fetchTagCatalog } from "@api/documents/tags";
import { buildWeakEtag } from "@api/etag";
import { listWorkspaceMembers } from "@api/workspaces/api";
import { Button } from "@/components/ui/button";
import { SpinnerIcon } from "@components/icons";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useNotifications } from "@components/providers/notifications";
import type { PresenceParticipant } from "@schema/presence";
import type { UploadManagerItem } from "@hooks/documents/uploadManager";

import { DocumentsPresenceIndicator } from "../presence/DocumentsPresenceIndicator";
import { useDocumentsPresence } from "../../hooks/useDocumentsPresence";
import { useDocumentsListParams } from "../../hooks/useDocumentsListParams";
import { useDocumentsView } from "../../hooks/useDocumentsView";
import { useDocumentsChangesStream } from "../../hooks/useDocumentsChangesStream";
import { DocumentsEmptyState } from "./DocumentsEmptyState";
import { DocumentsTable } from "./DocumentsTable";
import { useDocumentsColumns } from "./documentsColumns";
import { shortId } from "../../utils";
import type { DocumentRow, WorkspacePerson } from "../../types";

const MAX_DELTA_PAGES = 25;
const DELTA_LIMIT = 200;

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

type UploadItem = UploadManagerItem<DocumentUploadResponse>;

type RowMutation = "archive" | "restore" | "delete" | "assign" | "tags";

type HydratedChange = DocumentChangeEntry & { row?: DocumentListRow | null };

export function DocumentsTableView({
  workspaceId,
  currentUser,
  configMissing = false,
  processingPaused = false,
  toolbarActions,
  uploadItems,
  onUploadClick,
}: {
  workspaceId: string;
  currentUser: CurrentUser;
  configMissing?: boolean;
  processingPaused?: boolean;
  toolbarActions?: ReactNode;
  uploadItems?: UploadItem[];
  onUploadClick?: () => void;
}) {
  const { notifyToast } = useNotifications();
  const [deleteTarget, setDeleteTarget] = useState<DocumentRow | null>(null);
  const [pendingMutations, setPendingMutations] = useState<Record<string, Set<RowMutation>>>({});

  const presence = useDocumentsPresence({ workspaceId, enabled: Boolean(workspaceId) });
  const { page, perPage, sort, filters, joinOperator } = useDocumentsListParams();
  const documentsView = useDocumentsView({
    workspaceId,
    page,
    perPage,
    sort,
    filters,
    joinOperator,
    enabled: Boolean(workspaceId),
  });
  const {
    rows: documents,
    documentsById,
    pageCount,
    isLoading,
    isFetching,
    error,
    refreshSnapshot,
    updateRow,
    upsertRow,
    removeRow,
    setUploadProgress,
    cursor,
    setCursor,
  } = documentsView;

  const handledUploadsRef = useRef(new Set<string>());
  const completedUploadsRef = useRef(new Set<string>());

  const toolbarParticipants = useMemo(
    () => dedupeParticipants(presence.participants, presence.clientId),
    [presence.clientId, presence.participants],
  );

  const rowPresence = useMemo(
    () => mapPresenceByDocument(presence.participants, presence.clientId),
    [presence.clientId, presence.participants],
  );

  const membersQuery = useQuery({
    queryKey: ["documents-members", workspaceId],
    queryFn: ({ signal }) => listWorkspaceMembers(workspaceId, { limit: 200, signal }),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const people = useMemo<WorkspacePerson[]>(() => {
    const set = new Map<string, WorkspacePerson>();
    set.set(currentUser.id, {
      id: currentUser.id,
      label: currentUser.label,
      email: currentUser.email,
    });

    const members = membersQuery.data?.items ?? [];
    members.forEach((member) => {
      const id = member.user_id;
      if (!id) return;
      const label = id === currentUser.id ? currentUser.label : `Member ${shortId(id)}`;
      if (!set.has(id)) {
        set.set(id, { id, label, email: null });
      }
    });

    return Array.from(set.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [currentUser.email, currentUser.id, currentUser.label, membersQuery.data?.items]);

  const tagsQuery = useQuery({
    queryKey: ["documents-tags", workspaceId],
    queryFn: ({ signal }) =>
      fetchTagCatalog(workspaceId, { limit: 200, sort: '[{"id":"count","desc":true}]' }, signal),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const tagOptions = useMemo(
    () => tagsQuery.data?.items?.map((item) => item.tag) ?? [],
    [tagsQuery.data?.items],
  );

  useEffect(() => {
    if (!uploadItems?.length) return;
    uploadItems.forEach((item) => {
      const row = item.response?.listRow ?? null;
      const documentId = row?.id ?? null;
      if (row && !handledUploadsRef.current.has(item.id)) {
        handledUploadsRef.current.add(item.id);
        upsertRow(row);
      }

      if (documentId && item.status !== "succeeded" && item.status !== "failed" && item.status !== "cancelled") {
        setUploadProgress(documentId, item.progress.percent ?? 0);
      }

      if (documentId && item.status === "succeeded" && !completedUploadsRef.current.has(item.id)) {
        completedUploadsRef.current.add(item.id);
        setUploadProgress(documentId, null);
      }

      if (documentId && (item.status === "failed" || item.status === "cancelled") && !completedUploadsRef.current.has(item.id)) {
        completedUploadsRef.current.add(item.id);
        setUploadProgress(documentId, null);
        removeRow(documentId);
      }
    });
  }, [removeRow, setUploadProgress, upsertRow, uploadItems]);

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
      const url = resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`);
      openDownload(url);
    },
    [openDownload, workspaceId],
  );

  const onAssign = useCallback(
    async (documentId: string, assigneeId: string | null) => {
      const current = documentsById[documentId];
      if (!current) {
        notifyToast({
          title: "Unable to update assignee",
          description: "Document not found in the current list.",
          intent: "danger",
        });
        return;
      }

      const person = assigneeId ? people.find((entry) => entry.id === assigneeId) : null;
      const fallbackEmail = assigneeId ? `${assigneeId}@workspace.local` : "unknown@workspace.local";
      const optimisticAssignee = assigneeId
        ? { id: assigneeId, name: person?.label ?? null, email: person?.email ?? fallbackEmail }
        : null;

      const snapshot = current.assignee ?? null;
      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      markRowPending(documentId, "assign");
      updateRow(documentId, { assignee: optimisticAssignee });
      try {
        const updated = await patchWorkspaceDocument(
          workspaceId,
          documentId,
          { assigneeId },
          { ifMatch },
        );
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
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
    [applyDocumentUpdate, clearRowPending, documentsById, markRowPending, notifyToast, people, updateRow, workspaceId],
  );

  const onToggleTag = useCallback(
    async (documentId: string, tag: string) => {
      const current = documentsById[documentId];
      if (!current) return;
      const tags = current.tags ?? [];
      const hasTag = tags.includes(tag);
      const nextTags = hasTag ? tags.filter((t) => t !== tag) : [...tags, tag];

      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      markRowPending(documentId, "tags");
      updateRow(documentId, { tags: nextTags });
      try {
        const updated = await patchDocumentTags(
          workspaceId,
          documentId,
          hasTag ? { remove: [tag] } : { add: [tag] },
          undefined,
          { ifMatch },
        );
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
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
    [applyDocumentUpdate, clearRowPending, documentsById, markRowPending, notifyToast, updateRow, workspaceId],
  );

  const onArchive = useCallback(
    async (documentId: string) => {
      const current = documentsById[documentId];
      if (!current) return;

      const snapshot = {
        status: current.status,
        updatedAt: current.updatedAt,
        activityAt: current.activityAt,
      };

      const now = new Date().toISOString();
      updateRow(documentId, { status: "archived", updatedAt: now, activityAt: now });

      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      markRowPending(documentId, "archive");
      try {
        const updated = await archiveWorkspaceDocument(workspaceId, documentId, { ifMatch });
        applyDocumentUpdate(documentId, updated);
        notifyToast({ title: "Document archived.", intent: "success", duration: 4000 });
      } catch (error) {
        updateRow(documentId, snapshot);
        notifyToast({
          title: error instanceof Error ? error.message : "Unable to archive document.",
          intent: "danger",
        });
      } finally {
        clearRowPending(documentId, "archive");
      }
    },
    [applyDocumentUpdate, clearRowPending, documentsById, markRowPending, notifyToast, updateRow, workspaceId],
  );

  const onRestore = useCallback(
    async (documentId: string) => {
      const current = documentsById[documentId];
      if (!current) return;
      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      markRowPending(documentId, "restore");
      try {
        const updated = await restoreWorkspaceDocument(workspaceId, documentId, { ifMatch });
        applyDocumentUpdate(documentId, updated);
        notifyToast({ title: "Document restored.", intent: "success", duration: 4000 });
      } catch (error) {
        notifyToast({
          title: error instanceof Error ? error.message : "Unable to restore document.",
          intent: "danger",
        });
      } finally {
        clearRowPending(documentId, "restore");
      }
    },
    [applyDocumentUpdate, clearRowPending, documentsById, markRowPending, notifyToast, workspaceId],
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
    markRowPending(deleteTarget.id, "delete");
    try {
      await deleteWorkspaceDocument(workspaceId, deleteTarget.id, { ifMatch });
      removeRow(deleteTarget.id);
      notifyToast({ title: "Document deleted.", intent: "success", duration: 4000 });
      setDeleteTarget(null);
    } catch (error) {
      notifyToast({
        title: error instanceof Error ? error.message : "Unable to delete document.",
        intent: "danger",
      });
    } finally {
      clearRowPending(deleteTarget.id, "delete");
    }
  }, [clearRowPending, deleteTarget, markRowPending, notifyToast, removeRow, workspaceId]);

  const hydrateChange = useCallback(
    async (entry: DocumentChangeEntry): Promise<HydratedChange> => {
      if (entry.type === "document.deleted") {
        return entry;
      }
      if (!entry.documentId) {
        return entry;
      }
      if (entry.row) {
        return entry as HydratedChange;
      }
      try {
        const row = await fetchWorkspaceDocumentRowById(workspaceId, entry.documentId);
        return { ...entry, row };
      } catch {
        return entry;
      }
    },
    [workspaceId],
  );

  const applyIncomingChanges = useCallback(
    (entries: HydratedChange[], nextCursor?: string | null) => {
      let appliedCursor = cursor;
      entries.forEach((entry) => {
        if (entry.type === "document.changed") {
          if (entry.row) {
            upsertRow(entry.row);
          }
        } else if (entry.type === "document.deleted") {
          if (entry.documentId) {
            removeRow(entry.documentId);
          }
        }
        if (entry.cursor) {
          appliedCursor = entry.cursor;
        }
      });
      if (entries.length === 0 && nextCursor) {
        appliedCursor = nextCursor;
      }
      if (appliedCursor) {
        setCursor(appliedCursor);
      }
    },
    [cursor, removeRow, setCursor, upsertRow],
  );

  const catchUp = useCallback(async () => {
    if (!cursor || !workspaceId) return;
    let nextCursor = cursor;
    try {
      for (let pageIndex = 0; pageIndex < MAX_DELTA_PAGES; pageIndex += 1) {
        const changes = await fetchWorkspaceDocumentChanges(workspaceId, {
          cursor: nextCursor,
          limit: DELTA_LIMIT,
          includeRows: true,
        });
        const items = changes.items ?? [];
        const hydrated = await Promise.all(items.map(hydrateChange));
        applyIncomingChanges(hydrated, changes.nextCursor ?? null);
        nextCursor = changes.nextCursor ?? nextCursor;
        if (items.length === 0) {
          break;
        }
        if (pageIndex === MAX_DELTA_PAGES - 1) {
          void refreshSnapshot();
        }
      }
    } catch (err) {
      if (err instanceof DocumentChangesResyncError) {
        if (err.latestCursor) {
          setCursor(err.latestCursor);
        }
        void refreshSnapshot();
      }
    }
  }, [applyIncomingChanges, cursor, hydrateChange, refreshSnapshot, setCursor, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;
    const handleFocus = () => void catchUp();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void catchUp();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [catchUp, workspaceId]);

  useDocumentsChangesStream({
    workspaceId,
    cursor,
    enabled: Boolean(workspaceId && cursor),
    includeRows: true,
    onEvent: (change) => {
      void (async () => {
        const hydrated = await hydrateChange(change);
        applyIncomingChanges([hydrated]);
      })();
    },
    onReady: (nextCursor) => {
      if (nextCursor) {
        setCursor(nextCursor);
      }
    },
    onResyncRequired: (latestCursor) => {
      if (latestCursor) {
        setCursor(latestCursor);
      }
      void refreshSnapshot();
    },
  });

  const columns = useDocumentsColumns({
    people,
    tagOptions,
    rowPresence,
    onAssign,
    onToggleTag,
    onArchive,
    onRestore,
    onDeleteRequest,
    onDownloadOutput: handleDownloadOutput,
    onDownloadOriginal: handleDownloadOriginal,
    isRowActionPending: isRowMutationPending,
  });

  const hasDocuments = documents.length > 0;
  const showInitialLoading = isLoading && !hasDocuments;
  const showInitialError = Boolean(error) && !hasDocuments;
  const hasActiveFilters = Boolean(filters?.length);

  const toolbarStatus = (
    <div className="flex h-4 w-4 items-center justify-center">
      {isFetching ? (
        <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : error && hasDocuments ? (
        <AlertTriangle
          className="h-4 w-4 text-destructive"
          aria-label="Document list refresh failed"
        />
      ) : null}
    </div>
  );

  const statusBadges = (
    <>
      {configMissing ? (
        <Badge variant="secondary" className="text-xs">
          No active configuration
        </Badge>
      ) : null}
      {processingPaused ? (
        <Badge variant="secondary" className="text-xs">
          Processing paused
        </Badge>
      ) : null}
    </>
  );

  const toolbarContent = (
    <div className="flex flex-wrap items-center gap-2">
      <DocumentsPresenceIndicator
        participants={toolbarParticipants}
        connectionState={presence.connectionState}
      />
      {statusBadges}
      {toolbarActions}
      {toolbarStatus}
    </div>
  );

  if (showInitialLoading) {
    return (
      <div className="min-h-[240px]">
        <DocumentsEmptyState
          title="Loading documents"
          description="Fetching the latest processing activity."
        />
      </div>
    );
  }

  if (showInitialError) {
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

  if (!hasDocuments && !hasActiveFilters) {
    return (
      <DocumentsEmptyState
        title="No documents yet"
        description="Upload a spreadsheet to start processing."
        action={onUploadClick ? { label: "Upload", onClick: onUploadClick } : undefined}
      />
    );
  }

  const deletePending =
    deleteTarget ? pendingMutations[deleteTarget.id]?.has("delete") ?? false : false;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
      <DocumentsTable
        data={documents}
        pageCount={pageCount}
        columns={columns}
        toolbarActions={toolbarContent}
      />
      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => (!open ? onDeleteCancel() : undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete document?</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `This permanently deletes "${deleteTarget.name}". This action cannot be undone.`
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
