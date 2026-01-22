import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { parseAsStringEnum, useQueryState } from "nuqs";

import { resolveApiUrl } from "@/api/client";
import {
  deleteWorkspaceDocument,
  fetchWorkspaceDocumentRowById,
  patchWorkspaceDocument,
  type DocumentChangeEntry,
  type DocumentListRow,
  type DocumentRecord,
  type DocumentUploadResponse,
} from "@/api/documents";
import { patchDocumentTags, fetchTagCatalog } from "@/api/documents/tags";
import { buildWeakEtag } from "@/api/etag";
import { listWorkspaceMembers } from "@/api/workspaces/api";
import { Button } from "@/components/ui/button";
import { SpinnerIcon } from "@/components/icons";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useNotifications } from "@/providers/notifications";
import { ApiError } from "@/api/errors";
import type { PresenceParticipant } from "@/types/presence";
import type { UploadManagerItem } from "@/pages/Workspace/sections/Documents/hooks/uploadManager";
import type { components } from "@/types";

import { DocumentsPresenceIndicator } from "../presence/DocumentsPresenceIndicator";
import { useDocumentsListParams } from "../../hooks/useDocumentsListParams";
import { useDocumentsSelection } from "../../hooks/useDocumentsSelection";
import { useDocumentsView } from "../../hooks/useDocumentsView";
import { DocumentsConfigBanner } from "./DocumentsConfigBanner";
import { DocumentsEmptyState } from "./DocumentsEmptyState";
import { DocumentsTable } from "./DocumentsTable";
import { useDocumentsColumns } from "./documentsColumns";
import { DocumentsCommentsPane } from "../comments/DocumentsCommentsPane";
import { DocumentsPreviewDialog } from "../../preview/components/DocumentsPreviewDialog";
import { shortId } from "../../utils";
import type { DocumentRow, WorkspacePerson } from "../../types";
import { useWorkspaceDocumentsChanges } from "@/pages/Workspace/context/WorkspaceDocumentsStreamContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

type UploadItem = UploadManagerItem<DocumentUploadResponse>;
type TagCatalogPage = components["schemas"]["TagCatalogPage"];

type RowMutation = "delete" | "assign" | "tags";

type HydratedChange = DocumentChangeEntry & { row?: DocumentListRow | null };

function tagKey(value: string) {
  return value.trim().toLowerCase();
}

function mergeTagOptions(primary: readonly string[], secondary: readonly string[]) {
  const seen = new Set<string>();
  const out: string[] = [];

  const push = (raw: string) => {
    const normalized = raw.trim();
    const key = normalized.toLowerCase();
    if (!key) return;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(normalized);
  };

  primary.forEach(push);
  secondary.forEach(push);

  return out;
}

function hasTagOption(options: readonly string[], tag: string) {
  const k = tagKey(tag);
  if (!k) return false;
  return options.some((option) => tagKey(option) === k);
}

function isSameStringArray(a: readonly string[], b: readonly string[]) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

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
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<DocumentRow | null>(null);
  const [pendingMutations, setPendingMutations] = useState<Record<string, Set<RowMutation>>>({});

  const [filterFlag, setFilterFlag] = useQueryState(
    "filterFlag",
    parseAsStringEnum(["advancedFilters"]).withOptions({ clearOnDefault: true }),
  );
  const filterMode = filterFlag === "advancedFilters" ? "advanced" : "simple";
  const presence = useWorkspacePresence();
  const { page, perPage, sort, q, filters, joinOperator } = useDocumentsListParams({ filterMode });
  const documentsView = useDocumentsView({
    workspaceId,
    page,
    perPage,
    sort,
    q,
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
  } = documentsView;

  const {
    docId,
    isPreviewOpen,
    isCommentsOpen,
    openPreview,
    openComments,
    closePreview,
    closeComments,
  } = useDocumentsSelection();
  const { sendSelection } = presence;

  useEffect(() => {
    sendSelection({ documentId: docId ?? null });
  }, [docId, sendSelection]);

  const onToggleFilterMode = useCallback(() => {
    setFilterFlag(filterFlag === "advancedFilters" ? null : "advancedFilters");
  }, [filterFlag, setFilterFlag]);

  const handledUploadsRef = useRef(new Set<string>());
  const completedUploadsRef = useRef(new Set<string>());

  const documentsParticipants = useMemo(
    () => filterParticipantsByPage(presence.participants, "documents"),
    [presence.participants],
  );

  const toolbarParticipants = useMemo(
    () => dedupeParticipants(documentsParticipants, presence.clientId),
    [documentsParticipants, presence.clientId],
  );

  const rowPresence = useMemo(
    () => mapPresenceByDocument(documentsParticipants, presence.clientId),
    [documentsParticipants, presence.clientId],
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

  const catalogTagOptions = useMemo(
    () => tagsQuery.data?.items?.map((item) => item.tag) ?? [],
    [tagsQuery.data?.items],
  );

  const tagOptionsWorkspaceRef = useRef(workspaceId);
  const [tagOptions, setTagOptions] = useState<string[]>(catalogTagOptions);

  useEffect(() => {
    setTagOptions((current) => {
      if (tagOptionsWorkspaceRef.current !== workspaceId) {
        tagOptionsWorkspaceRef.current = workspaceId;
        return mergeTagOptions(catalogTagOptions, []);
      }

      const merged = mergeTagOptions(catalogTagOptions, current);
      return isSameStringArray(merged, current) ? current : merged;
    });
  }, [catalogTagOptions, workspaceId]);

  const handleTagOptionsChange = useCallback((nextOptions: string[]) => {
    setTagOptions((current) => {
      const merged = mergeTagOptions(nextOptions, current);
      return isSameStringArray(merged, current) ? current : merged;
    });
  }, []);

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
        updatedAt: updated.updatedAt,
        activityAt,
        version: updated.version,
        etag,
        tags: updated.tags,
        assignee: updated.assignee ?? null,
        uploader: updated.uploader ?? null,
        lastRun: updated.lastRun ?? null,
        lastRunMetrics: updated.lastRunMetrics ?? null,
        lastRunTableColumns: updated.lastRunTableColumns ?? null,
        lastRunFields: updated.lastRunFields ?? null,
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
      const runId = document.lastRun?.status === "succeeded" ? document.lastRun.id : null;
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
      const isNewOption = !hasTag && !hasTagOption(tagOptions, tag);

      const ifMatch = current.etag ?? buildWeakEtag(documentId, String(current.version));
      markRowPending(documentId, "tags");
      updateRow(documentId, { tags: nextTags });
      if (isNewOption) {
        setTagOptions((currentOptions) => {
          const merged = mergeTagOptions(currentOptions, [tag]);
          return isSameStringArray(merged, currentOptions) ? currentOptions : merged;
        });
      }
      try {
        const updated = await patchDocumentTags(
          workspaceId,
          documentId,
          hasTag ? { remove: [tag] } : { add: [tag] },
          undefined,
          { ifMatch },
        );
        applyDocumentUpdate(documentId, updated);
        if (isNewOption) {
          queryClient.setQueryData<TagCatalogPage | undefined>(
            ["documents-tags", workspaceId],
            (currentCatalog) => {
              if (!currentCatalog) return currentCatalog;
              const exists = currentCatalog.items.some((item) => tagKey(item.tag) === tagKey(tag));
              if (exists) return currentCatalog;
              return {
                ...currentCatalog,
                items: [...currentCatalog.items, { tag, document_count: 1 }],
              };
            },
          );
          queryClient.invalidateQueries({ queryKey: ["documents-tags", workspaceId] });
        }
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
    [
      applyDocumentUpdate,
      clearRowPending,
      documentsById,
      markRowPending,
      notifyToast,
      queryClient,
      tagOptions,
      updateRow,
      workspaceId,
    ],
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
    (entries: HydratedChange[]) => {
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
      });
    },
    [removeRow, upsertRow],
  );

  useWorkspaceDocumentsChanges(
    useCallback(
      (change) => {
        void (async () => {
          const hydrated = await hydrateChange(change);
          applyIncomingChanges([hydrated]);
        })();
      },
      [applyIncomingChanges, hydrateChange],
    ),
  );

  const handleTogglePreview = useCallback(
    (documentId: string) => {
      if (docId === documentId && isPreviewOpen) {
        closePreview();
        return;
      }
      openPreview(documentId);
    },
    [closePreview, docId, isPreviewOpen, openPreview],
  );

  const handleToggleComments = useCallback(
    (documentId: string) => {
      if (docId === documentId && isCommentsOpen) {
        closeComments();
        return;
      }
      openComments(documentId);
    },
    [closeComments, docId, isCommentsOpen, openComments],
  );

  const columns = useDocumentsColumns({
    filterMode,
    people,
    tagOptions,
    rowPresence,
    selectedDocumentId: docId,
    isPreviewOpen,
    isCommentsOpen,
    onOpenPreview: openPreview,
    onTogglePreview: handleTogglePreview,
    onToggleComments: handleToggleComments,
    onAssign,
    onToggleTag,
    onTagOptionsChange: handleTagOptionsChange,
    onDeleteRequest,
    onDownloadOutput: handleDownloadOutput,
    onDownloadOriginal: handleDownloadOriginal,
    isRowActionPending: isRowMutationPending,
  });

  const hasDocuments = documents.length > 0;
  const showInitialLoading = isLoading && !hasDocuments;
  const showInitialError = Boolean(error) && !hasDocuments;

  const previewFallbackQuery = useQuery({
    queryKey: ["documents-preview-row", workspaceId, docId],
    queryFn: ({ signal }) =>
      docId
        ? fetchWorkspaceDocumentRowById(workspaceId, docId, {}, signal)
        : Promise.resolve(null),
    enabled: Boolean(workspaceId && docId && !documentsById[docId]),
    staleTime: 30_000,
  });

  const previewDetailsQuery = useQuery({
    queryKey: ["documents-preview-details", workspaceId, docId],
    queryFn: ({ signal }) =>
      docId
        ? fetchWorkspaceDocumentRowById(
            workspaceId,
            docId,
            {
              includeRunMetrics: true,
              includeRunTableColumns: true,
              includeRunFields: true,
            },
            signal,
          )
        : Promise.resolve(null),
    enabled: Boolean(workspaceId && docId && isPreviewOpen),
    staleTime: 30_000,
  });

  const previewFallback = previewFallbackQuery.data && docId ? previewFallbackQuery.data : null;
  const previewDetails = previewDetailsQuery.data && docId ? previewDetailsQuery.data : null;
  const baseDocument = docId ? documentsById[docId] ?? previewFallback ?? null : null;
  const selectedDocument = useMemo(() => {
    if (!docId) return null;
    if (!baseDocument && !previewDetails) return null;
    return {
      ...(baseDocument ?? {}),
      ...(previewDetails ?? {}),
      uploadProgress: baseDocument?.uploadProgress ?? null,
    } as DocumentRow;
  }, [baseDocument, docId, previewDetails]);
  const previewErrorMessage = useMemo(() => {
    if (!previewFallbackQuery.isError) return null;
    const error = previewFallbackQuery.error;
    if (error instanceof ApiError) {
      if (error.status === 404) {
        return "We couldn’t find that document. It may have been deleted.";
      }
      if (error.status === 403) {
        return "You don’t have access to that document.";
      }
    }
    return "We couldn’t load that document. Try again.";
  }, [previewFallbackQuery.error, previewFallbackQuery.isError]);
  const isPreviewLoading = Boolean(docId && !selectedDocument && previewFallbackQuery.isLoading);
  const isCommentsLoading = isPreviewLoading;
  const showPreview = Boolean(docId && isPreviewOpen);
  const showComments = Boolean(docId && isCommentsOpen);

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

  const configBanner = configMissing ? <DocumentsConfigBanner workspaceId={workspaceId} /> : null;

  const deletePending =
    deleteTarget ? pendingMutations[deleteTarget.id]?.has("delete") ?? false : false;

  const tableContent = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col px-6 pb-6 pt-2">
        {configBanner}
        <DocumentsTable
          data={documents}
          pageCount={pageCount}
          columns={columns}
          filterMode={filterMode}
          onToggleFilterMode={onToggleFilterMode}
          toolbarActions={toolbarContent}
        />
      </div>
    </div>
  );

  const commentsContent = (
    <DocumentsCommentsPane
      workspaceId={workspaceId}
      document={selectedDocument}
      onClose={closeComments}
      isLoading={isCommentsLoading}
      errorMessage={previewErrorMessage}
    />
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        {tableContent}
        {showComments ? (
          <div className="min-h-0 w-[360px] min-w-[320px] flex-shrink-0 overflow-hidden">
            {commentsContent}
          </div>
        ) : null}
      </div>
      <DocumentsPreviewDialog
        open={showPreview}
        onOpenChange={(open) => {
          if (!open) closePreview();
        }}
        workspaceId={workspaceId}
        document={selectedDocument}
        onDownloadOriginal={handleDownloadOriginal}
        onDownloadOutput={handleDownloadOutput}
        isLoading={isPreviewLoading}
        errorMessage={previewErrorMessage}
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

function getPresencePage(participant: PresenceParticipant) {
  const presence = participant.presence;
  if (!presence || typeof presence !== "object") return null;
  const page = presence["page"];
  return typeof page === "string" ? page : null;
}

function filterParticipantsByPage(participants: PresenceParticipant[], page: string) {
  return participants.filter((participant) => getPresencePage(participant) === page);
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
