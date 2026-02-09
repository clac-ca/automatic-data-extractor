import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { resolveApiUrl } from "@/api/client";
import {
  deleteWorkspaceDocumentsBatch,
  deleteWorkspaceDocument,
  fetchWorkspaceDocumentRowsByIdFilter,
  patchWorkspaceDocument,
  restoreWorkspaceDocument,
  restoreWorkspaceDocumentsBatch,
  type DocumentChangeNotification,
  type DocumentRecord,
  type DocumentUploadResponse,
} from "@/api/documents";
import { patchDocumentTags, patchDocumentTagsBatch, fetchTagCatalog } from "@/api/documents/tags";
import {
  createDocumentView as createSavedDocumentView,
  updateDocumentView as updateSavedDocumentView,
  type DocumentViewRecord,
} from "@/api/documents/views";
import { ApiError, groupProblemDetailsErrors } from "@/api/errors";
import { cancelRun, createRun, createRunsBatch } from "@/api/runs/api";
import type { RunStreamOptions } from "@/api/runs/api";
import { listWorkspaceMembers } from "@/api/workspaces/api";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useNotifications } from "@/providers/notifications";
import type { components } from "@/types";
import type { UploadManagerItem } from "@/pages/Workspace/sections/Documents/list/upload/useUploadManager";
import {
  filterParticipantsByPage,
  mapPresenceByDocument,
} from "@/pages/Workspace/hooks/presence/presenceParticipants";

import { inferFileType, shortId } from "../../shared/utils";
import { partitionDocumentChanges } from "../../shared/documentChanges";
import type { DocumentRow, WorkspacePerson } from "../../shared/types";
import { useDocumentsListParams } from "../hooks/useDocumentsListParams";
import { useDocumentsListData } from "../hooks/useDocumentsListData";
import { useDocumentsDeltaSync } from "../../shared/hooks/useDocumentsDeltaSync";
import { getRenameDocumentErrorMessage, useRenameDocumentMutation } from "../../shared/hooks/useRenameDocumentMutation";
import { buildDocumentDetailUrl } from "../../shared/navigation";
import { RenameDocumentDialog } from "../../shared/ui/RenameDocumentDialog";
import { TagSelector } from "../../shared/ui/TagSelector";
import { DocumentsConfigBanner } from "./DocumentsConfigBanner";
import { DocumentsDialogs } from "./DocumentsDialogs";
import { DocumentsEmptyState } from "./DocumentsEmptyState";
import { DocumentsTable } from "./DocumentsTable";
import { DocumentsToolbar } from "./DocumentsToolbar";
import { DocumentsViewsDropdown } from "./DocumentsViewsDropdown";
import { useDocumentsColumns } from "./documentsColumns";
import { useDocumentsBulkActions } from "./useDocumentsBulkActions";
import { useDocumentsRowActions } from "./useDocumentsRowActions";
import { buildDocumentRowActions, toContextMenuItems } from "./actions/documentRowActions";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useDataTable } from "@/hooks/use-data-table";
import { DEFAULT_PAGE_SIZE, DEFAULT_SORTING } from "../../shared/constants";
import { useDocumentViews } from "../hooks/useDocumentViews";
import {
  ReprocessPreflightDialog,
  type ReprocessTargetDocument,
} from "../upload/ReprocessPreflightDialog";

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

type UploadItem = UploadManagerItem<DocumentUploadResponse>;
type TagCatalogPage = components["schemas"]["TagCatalogPage"];

type BulkTagPatch = {
  add: string[];
  remove: string[];
};

const BULK_DOWNLOAD_WARNING_THRESHOLD = 12;
const BULK_DOWNLOAD_DELAY_MS = 80;
const ASSIGN_CHOICE_UNASSIGN = "__unassign__";

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

function uniqueDocumentIds(documents: readonly DocumentRow[]) {
  return Array.from(new Set(documents.map((document) => document.id).filter(Boolean)));
}

function applyTagPatch(
  currentTags: readonly string[] | null | undefined,
  patch: BulkTagPatch,
) {
  const removeKeys = new Set(patch.remove.map(tagKey).filter(Boolean));
  const kept = (currentTags ?? []).filter((tag) => !removeKeys.has(tagKey(tag)));
  return mergeTagOptions(kept, patch.add);
}

function normalizeBulkTagPatch(patch: BulkTagPatch): BulkTagPatch {
  const add = mergeTagOptions(patch.add, []);
  const addKeys = new Set(add.map(tagKey).filter(Boolean));
  const remove = mergeTagOptions(
    patch.remove.filter((tag) => !addKeys.has(tagKey(tag))),
    [],
  );
  return { add, remove };
}

function isSameStringArray(a: readonly string[], b: readonly string[]) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function deriveFileType(name: string): DocumentRow["fileType"] {
  return inferFileType(name);
}

function extractRestoreConflict(error: ApiError): { message: string; suggestedName: string | null } {
  const fallbackMessage = error.message || "Unable to restore document.";
  const detail = error.problem?.detail;
  const message = typeof detail === "string" && detail.trim().length > 0 ? detail : fallbackMessage;

  const groupedErrors = groupProblemDetailsErrors(error.problem?.errors);
  const firstSuggestedName = groupedErrors.suggestedName?.[0];
  const suggestedName =
    typeof firstSuggestedName === "string" && firstSuggestedName.trim().length > 0
      ? firstSuggestedName
      : null;

  return { message, suggestedName };
}

function isRunActive(document: DocumentRow) {
  return document.lastRun?.status === "queued" || document.lastRun?.status === "running";
}

function toReprocessTargetDocument(document: DocumentRow): ReprocessTargetDocument {
  return {
    id: document.id,
    name: document.name,
    fileType: document.fileType,
  };
}

export function DocumentsTableContainer({
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
  const { hasPermission } = useWorkspaceContext();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [deleteTarget, setDeleteTarget] = useState<DocumentRow | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<DocumentRow | null>(null);
  const [restoreRenameTarget, setRestoreRenameTarget] = useState<DocumentRow | null>(null);
  const [restoreRenameInitialName, setRestoreRenameInitialName] = useState("");
  const [restoreRenameError, setRestoreRenameError] = useState<string | null>(null);
  const [saveAsOpen, setSaveAsOpen] = useState(false);
  const [saveAsName, setSaveAsName] = useState("");
  const [saveAsVisibility, setSaveAsVisibility] = useState<"private" | "public">("private");
  const [saveAsError, setSaveAsError] = useState<string | null>(null);
  const [viewRenameTarget, setViewRenameTarget] = useState<DocumentViewRecord | null>(null);
  const [viewRenameName, setViewRenameName] = useState("");
  const [viewRenameError, setViewRenameError] = useState<string | null>(null);
  const [isViewRenameSubmitting, setIsViewRenameSubmitting] = useState(false);
  const [viewDeleteTarget, setViewDeleteTarget] = useState<DocumentViewRecord | null>(null);
  const [isViewDeleteSubmitting, setIsViewDeleteSubmitting] = useState(false);
  const [reprocessTargets, setReprocessTargets] = useState<ReprocessTargetDocument[]>([]);
  const [isReprocessSubmitting, setIsReprocessSubmitting] = useState(false);
  const [selectionResetToken, setSelectionResetToken] = useState(0);
  const [inlineRenameRequest, setInlineRenameRequest] = useState<{
    documentId: string;
    nonce: number;
  } | null>(null);
  const renameMutation = useRenameDocumentMutation({ workspaceId });
  const canManagePublicViews = hasPermission("workspace.documents.views.public.manage");
  const {
    bulkAssignTargets,
    setBulkAssignTargets,
    bulkAssignChoice,
    setBulkAssignChoice,
    isBulkAssignSubmitting,
    setIsBulkAssignSubmitting,
    bulkTagTargets,
    setBulkTagTargets,
    bulkTagAdd,
    setBulkTagAdd,
    bulkTagRemove,
    setBulkTagRemove,
    isBulkTagSubmitting,
    setIsBulkTagSubmitting,
    bulkDeleteTargets,
    setBulkDeleteTargets,
    isBulkDeleteSubmitting,
    setIsBulkDeleteSubmitting,
    bulkRestoreTargets,
    setBulkRestoreTargets,
    isBulkRestoreSubmitting,
    setIsBulkRestoreSubmitting,
    resetBulkActions,
  } = useDocumentsBulkActions();
  const {
    pendingMutations,
    markRowPending,
    clearRowPending,
    isRowMutationPending,
    resetRowMutations,
  } = useDocumentsRowActions();

  const presence = useWorkspacePresence();
  const { page, perPage, sort, q, lifecycle, filters, joinOperator } = useDocumentsListParams({
    currentUserId: currentUser.id,
  });
  const filtersKey = useMemo(() => (filters?.length ? JSON.stringify(filters) : ""), [filters]);
  const viewKey = useMemo(
    () =>
      [workspaceId, page, perPage, sort ?? "", q ?? "", lifecycle, filtersKey, joinOperator ?? ""].join(
        "|",
      ),
    [filtersKey, joinOperator, lifecycle, page, perPage, q, sort, workspaceId],
  );
  const documentsView = useDocumentsListData({
    workspaceId,
    page,
    perPage,
    sort,
    q,
    lifecycle,
    filters,
    joinOperator,
    enabled: Boolean(workspaceId),
  });
  const {
    rows: documents,
    documentsById,
    changesCursor,
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
  const [updatesAvailable, setUpdatesAvailable] = useState(false);

  const openDocument = useCallback(
    (
      documentId: string,
      target: "activity" | "preview" = "activity",
      options: { activityFilter?: "comments" | "events" } = {},
    ) => {
      const url = buildDocumentDetailUrl(workspaceId, documentId, {
        tab: target,
        activityFilter: options.activityFilter ?? "all",
      });
      navigate(url);
    },
    [navigate, workspaceId],
  );

  const handledUploadsRef = useRef(new Set<string>());
  const completedUploadsRef = useRef(new Set<string>());
  const inlineRenameNonceRef = useRef(0);

  useEffect(() => {
    setDeleteTarget(null);
    setRestoreTarget(null);
    setRestoreRenameTarget(null);
    setRestoreRenameInitialName("");
    setRestoreRenameError(null);
    setSaveAsOpen(false);
    setSaveAsName("");
    setSaveAsVisibility("private");
    setSaveAsError(null);
    setViewRenameTarget(null);
    setViewRenameName("");
    setViewRenameError(null);
    setIsViewRenameSubmitting(false);
    setViewDeleteTarget(null);
    setIsViewDeleteSubmitting(false);
    resetRowMutations();
    setReprocessTargets([]);
    setIsReprocessSubmitting(false);
    resetBulkActions();
    setSelectionResetToken(0);
    setInlineRenameRequest(null);
    setUpdatesAvailable(false);
    handledUploadsRef.current.clear();
    completedUploadsRef.current.clear();
  }, [resetBulkActions, resetRowMutations, workspaceId]);

  useEffect(() => {
    setUpdatesAvailable(false);
  }, [viewKey]);

  const documentsParticipants = useMemo(
    () => filterParticipantsByPage(presence.participants, "documents"),
    [presence.participants],
  );

  const rowPresence = useMemo(
    () =>
      mapPresenceByDocument(documentsParticipants, {
        currentUserId: currentUser.id,
        currentClientId: presence.clientId,
      }),
    [currentUser.id, documentsParticipants, presence.clientId],
  );

  const membersQuery = useQuery({
    queryKey: ["documents-members", workspaceId],
    queryFn: ({ signal }) => listWorkspaceMembers(workspaceId, { limit: 200, signal }),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const people = useMemo<WorkspacePerson[]>(() => {
    const peopleById = new Map<string, WorkspacePerson>();

    const upsertPerson = (id: string, label: string, email: string | null) => {
      const existing = peopleById.get(id);
      if (!existing) {
        peopleById.set(id, { id, label, email });
        return;
      }
      peopleById.set(id, {
        id,
        label: existing.label || label,
        email: existing.email ?? email,
      });
    };

    upsertPerson(currentUser.id, currentUser.label, currentUser.email);

    documents.forEach((document) => {
      [document.assignee, document.uploader].forEach((user) => {
        if (!user?.id) return;
        const label = user.name?.trim() || user.email || `Member ${shortId(user.id)}`;
        upsertPerson(user.id, label, user.email);
      });
    });

    const members = membersQuery.data?.items ?? [];
    members.forEach((member) => {
      const id = member.user_id;
      if (!id) return;

      const memberUser = member.user;
      const email = memberUser?.email ?? peopleById.get(id)?.email ?? null;
      const label =
        id === currentUser.id
          ? currentUser.label
          : memberUser?.display_name?.trim() || email || peopleById.get(id)?.label || `Member ${shortId(id)}`;

      upsertPerson(id, label, email);
    });

    return Array.from(peopleById.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [currentUser.email, currentUser.id, currentUser.label, documents, membersQuery.data?.items]);

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
      const updates: Partial<DocumentRow> = {
        name: updated.name,
        fileType: deriveFileType(updated.name),
        updatedAt: updated.updatedAt,
        activityAt,
        deletedAt: updated.deletedAt ?? null,
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

  const openDownload = useCallback((url: string) => {
    if (typeof window === "undefined" || typeof document === "undefined") return;
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    window.setTimeout(() => {
      anchor.remove();
    }, 0);
  }, []);

  const handleDownloadLatest = useCallback(
    (document: DocumentRow) => {
      const url = resolveApiUrl(
        `/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`,
      );
      openDownload(url);
    },
    [openDownload, workspaceId],
  );

  const getOriginalDownloadUrl = useCallback(
    (document: DocumentRow) => {
      return resolveApiUrl(
        `/api/v1/workspaces/${workspaceId}/documents/${document.id}/original/download`,
      );
    },
    [workspaceId],
  );

  const handleDownloadOriginal = useCallback(
    (document: DocumentRow) => {
      openDownload(getOriginalDownloadUrl(document));
    },
    [getOriginalDownloadUrl, openDownload],
  );

  const startBulkDownloads = useCallback(
    (urls: string[], label: string) => {
      if (urls.length === 0) {
        notifyToast({
          title: "No files available",
          description: `No eligible documents were found to ${label}.`,
          intent: "warning",
        });
        return;
      }

      if (urls.length >= BULK_DOWNLOAD_WARNING_THRESHOLD) {
        notifyToast({
          title: `Preparing ${urls.length} downloads`,
          description: "Your browser may ask for permission to download multiple files.",
          intent: "warning",
        });
      }

      urls.forEach((url, index) => {
        window.setTimeout(() => {
          openDownload(url);
        }, index * BULK_DOWNLOAD_DELAY_MS);
      });
      notifyToast({
        title: "Download started",
        description: `${urls.length} file${urls.length === 1 ? "" : "s"} queued for download.`,
        intent: "success",
      });
    },
    [notifyToast, openDownload],
  );

  const onBulkDownloadRequest = useCallback(
    (selected: DocumentRow[]) => {
      const urls = uniqueDocumentIds(selected).map((documentId) =>
        resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/${documentId}/download`),
      );
      startBulkDownloads(urls, "download files");
    },
    [startBulkDownloads, workspaceId],
  );

  const onBulkDownloadOriginalRequest = useCallback(
    (selected: DocumentRow[]) => {
      const uniqueDocuments = Array.from(
        new Map(selected.map((document) => [document.id, document])).values(),
      );
      const urls = uniqueDocuments.map((document) => getOriginalDownloadUrl(document));
      startBulkDownloads(urls, "download original files");
    },
    [getOriginalDownloadUrl, startBulkDownloads],
  );

  const onReprocessRequest = useCallback((document: DocumentRow) => {
    setReprocessTargets([toReprocessTargetDocument(document)]);
  }, []);

  const onBulkReprocessRequest = useCallback((selected: DocumentRow[]) => {
    if (selected.length === 0) return;
    setReprocessTargets(selected.map((document) => toReprocessTargetDocument(document)));
  }, []);

  const onCancelRunRequest = useCallback(
    async (document: DocumentRow) => {
      const runId = isRunActive(document) ? document.lastRun?.id : null;
      if (!runId) {
        notifyToast({
          title: "Run is no longer active",
          description: "Only queued or running runs can be cancelled.",
          intent: "warning",
        });
        return;
      }

      markRowPending(document.id, "run");
      try {
        const cancelled = await cancelRun(workspaceId, runId);
        const fallbackCreatedAt = document.lastRun?.createdAt ?? new Date().toISOString();
        updateRow(document.id, {
          lastRun: {
            id: cancelled.id,
            status: "cancelled",
            createdAt: cancelled.created_at ?? fallbackCreatedAt,
            startedAt: cancelled.started_at ?? null,
            completedAt: cancelled.completed_at ?? new Date().toISOString(),
            errorMessage: cancelled.failure_message ?? "Run cancelled by user",
          },
        });
        notifyToast({
          title: "Run cancelled",
          description: `${document.name} was cancelled.`,
          intent: "success",
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          notifyToast({
            title: "Run already finished",
            description: `${document.name} is already in a terminal state.`,
            intent: "warning",
          });
          void refreshSnapshot();
          return;
        }
        notifyToast({
          title: "Unable to cancel run",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
        void refreshSnapshot();
      } finally {
        clearRowPending(document.id, "run");
      }
    },
    [clearRowPending, markRowPending, notifyToast, refreshSnapshot, updateRow],
  );

  const onBulkCancelRequest = useCallback(
    async (selected: DocumentRow[]) => {
      const cancellable = selected
        .filter((document) => isRunActive(document) && Boolean(document.lastRun?.id))
        .map((document) => ({
          document,
          runId: document.lastRun?.id as string,
        }));
      if (cancellable.length === 0) {
        notifyToast({
          title: "No active runs selected",
          description: "Select queued or running rows to cancel.",
          intent: "warning",
        });
        return;
      }

      cancellable.forEach(({ document }) => markRowPending(document.id, "run"));
      try {
        const settled = await Promise.allSettled(
          cancellable.map(({ runId }) => cancelRun(workspaceId, runId)),
        );

        let cancelledCount = 0;
        let skippedCount = 0;
        let failedCount = 0;

        settled.forEach((result, index) => {
          const target = cancellable[index];
          if (!target) return;
          if (result.status === "fulfilled") {
            cancelledCount += 1;
            const fallbackCreatedAt = target.document.lastRun?.createdAt ?? new Date().toISOString();
            updateRow(target.document.id, {
              lastRun: {
                id: result.value.id,
                status: "cancelled",
                createdAt: result.value.created_at ?? fallbackCreatedAt,
                startedAt: result.value.started_at ?? null,
                completedAt: result.value.completed_at ?? new Date().toISOString(),
                errorMessage: result.value.failure_message ?? "Run cancelled by user",
              },
            });
            return;
          }
          if (result.reason instanceof ApiError && result.reason.status === 409) {
            skippedCount += 1;
            return;
          }
          failedCount += 1;
        });

        const summaryParts = [`${cancelledCount} cancelled`];
        if (skippedCount > 0) summaryParts.push(`${skippedCount} skipped`);
        if (failedCount > 0) summaryParts.push(`${failedCount} failed`);
        notifyToast({
          title: "Cancel runs complete",
          description: summaryParts.join(", "),
          intent: failedCount > 0 ? "warning" : "success",
        });
        if (failedCount > 0 || skippedCount > 0) {
          void refreshSnapshot();
        }
      } finally {
        cancellable.forEach(({ document }) => clearRowPending(document.id, "run"));
      }
    },
    [clearRowPending, markRowPending, notifyToast, refreshSnapshot, updateRow],
  );

  const onBulkAssignRequest = useCallback((selected: DocumentRow[]) => {
    const targets = selected.filter((document) => Boolean(document.id));
    if (targets.length === 0) return;
    setBulkAssignTargets(targets);
    setBulkAssignChoice("");
  }, []);

  const onBulkAssignCancel = useCallback(() => {
    if (isBulkAssignSubmitting) return;
    setBulkAssignTargets([]);
    setBulkAssignChoice("");
  }, [isBulkAssignSubmitting]);

  const onBulkAssignConfirm = useCallback(async () => {
    if (!bulkAssignChoice) {
      notifyToast({
        title: "Choose an assignee",
        description: "Select a person or choose Unassigned to continue.",
        intent: "warning",
      });
      return;
    }

    const assigneeId = bulkAssignChoice === ASSIGN_CHOICE_UNASSIGN ? null : bulkAssignChoice;
    const targets = uniqueDocumentIds(bulkAssignTargets);
    if (targets.length === 0) {
      onBulkAssignCancel();
      return;
    }

    const person = assigneeId ? people.find((entry) => entry.id === assigneeId) ?? null : null;
    const shouldApplyOptimistic = assigneeId === null || (Boolean(person?.email) && Boolean(person?.label));
    const optimisticAssignee =
      assigneeId === null
        ? null
        : shouldApplyOptimistic && person?.email
          ? { id: assigneeId, name: person.label, email: person.email }
          : null;
    const previousAssignees = new Map<string, DocumentRow["assignee"]>();
    const targetLabel = assigneeId === null ? "Unassigned" : (person?.label ?? "selected user");

    targets.forEach((documentId) => {
      previousAssignees.set(documentId, documentsById[documentId]?.assignee ?? null);
      markRowPending(documentId, "assign");
      if (shouldApplyOptimistic) {
        updateRow(documentId, { assignee: optimisticAssignee });
      }
    });

    setIsBulkAssignSubmitting(true);
    try {
      const settled = await Promise.allSettled(
        targets.map((documentId) =>
          patchWorkspaceDocument(workspaceId, documentId, { assigneeId }),
        ),
      );

      let updatedCount = 0;
      let failedCount = 0;
      settled.forEach((result, index) => {
        const documentId = targets[index];
        if (!documentId) return;
        if (result.status === "fulfilled") {
          updatedCount += 1;
          applyDocumentUpdate(documentId, result.value);
          return;
        }
        failedCount += 1;
        if (shouldApplyOptimistic) {
          updateRow(documentId, { assignee: previousAssignees.get(documentId) ?? null });
        }
      });

      notifyToast({
        title: "Bulk assignment complete",
        description:
          failedCount > 0
            ? `${updatedCount} updated to ${targetLabel}, ${failedCount} failed.`
            : `${updatedCount} document${updatedCount === 1 ? "" : "s"} assigned to ${targetLabel}.`,
        intent: failedCount > 0 ? "warning" : "success",
      });
      if (failedCount > 0) {
        void refreshSnapshot();
      }
      if (updatedCount > 0) {
        onBulkAssignCancel();
      }
    } catch (error) {
      targets.forEach((documentId) => {
        if (shouldApplyOptimistic) {
          updateRow(documentId, { assignee: previousAssignees.get(documentId) ?? null });
        }
      });
      notifyToast({
        title: "Unable to update assignees",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
    } finally {
      targets.forEach((documentId) => clearRowPending(documentId, "assign"));
      setIsBulkAssignSubmitting(false);
    }
  }, [
    applyDocumentUpdate,
    bulkAssignChoice,
    bulkAssignTargets,
    clearRowPending,
    documentsById,
    markRowPending,
    notifyToast,
    onBulkAssignCancel,
    people,
    refreshSnapshot,
    updateRow,
    workspaceId,
  ]);

  const onBulkTagRequest = useCallback((selected: DocumentRow[]) => {
    const targets = selected.filter((document) => Boolean(document.id));
    if (targets.length === 0) return;
    setBulkTagTargets(targets);
    setBulkTagAdd([]);
    setBulkTagRemove([]);
  }, []);

  const onBulkTagCancel = useCallback(() => {
    if (isBulkTagSubmitting) return;
    setBulkTagTargets([]);
    setBulkTagAdd([]);
    setBulkTagRemove([]);
  }, [isBulkTagSubmitting]);

  const onBulkTagConfirm = useCallback(async () => {
    const normalizedPatch = normalizeBulkTagPatch({ add: bulkTagAdd, remove: bulkTagRemove });
    if (normalizedPatch.add.length === 0 && normalizedPatch.remove.length === 0) {
      notifyToast({
        title: "No tag changes selected",
        description: "Choose tags to add and/or remove before applying.",
        intent: "warning",
      });
      return;
    }

    const targets = uniqueDocumentIds(bulkTagTargets);
    if (targets.length === 0) {
      onBulkTagCancel();
      return;
    }

    const previousTags = new Map<string, string[]>();
    const previousTagOptions = tagOptions;
    targets.forEach((documentId) => {
      markRowPending(documentId, "tags");
      const currentTags = documentsById[documentId]?.tags ?? [];
      previousTags.set(documentId, [...currentTags]);
      updateRow(documentId, { tags: applyTagPatch(currentTags, normalizedPatch) });
    });

    if (normalizedPatch.add.length > 0) {
      setTagOptions((currentOptions) => {
        const merged = mergeTagOptions(currentOptions, normalizedPatch.add);
        return isSameStringArray(merged, currentOptions) ? currentOptions : merged;
      });
    }

    setIsBulkTagSubmitting(true);
    try {
      const updatedDocuments = await patchDocumentTagsBatch(workspaceId, targets, {
        add: normalizedPatch.add.length > 0 ? normalizedPatch.add : undefined,
        remove: normalizedPatch.remove.length > 0 ? normalizedPatch.remove : undefined,
      });
      const updatedById = new Map(updatedDocuments.map((document) => [document.id, document]));
      targets.forEach((documentId) => {
        const updated = updatedById.get(documentId);
        if (!updated) return;
        applyDocumentUpdate(documentId, updated);
      });

      if (normalizedPatch.add.length > 0) {
        queryClient.setQueryData<TagCatalogPage | undefined>(
          ["documents-tags", workspaceId],
          (currentCatalog) => {
            if (!currentCatalog) return currentCatalog;
            const existingKeys = new Set(currentCatalog.items.map((item) => tagKey(item.tag)));
            const additions = normalizedPatch.add
              .filter((tag) => !existingKeys.has(tagKey(tag)))
              .map((tag) => ({ tag, document_count: targets.length }));
            if (additions.length === 0) return currentCatalog;
            return {
              ...currentCatalog,
              items: [...currentCatalog.items, ...additions],
            };
          },
        );
        queryClient.invalidateQueries({ queryKey: ["documents-tags", workspaceId] });
      }

      const changeParts: string[] = [];
      if (normalizedPatch.add.length > 0) {
        changeParts.push(`added ${normalizedPatch.add.length}`);
      }
      if (normalizedPatch.remove.length > 0) {
        changeParts.push(`removed ${normalizedPatch.remove.length}`);
      }
      notifyToast({
        title: "Bulk tags updated",
        description: `${targets.length} document${targets.length === 1 ? "" : "s"} updated (${changeParts.join(", ")}).`,
        intent: "success",
      });
      onBulkTagCancel();
    } catch (error) {
      targets.forEach((documentId) => {
        updateRow(documentId, { tags: previousTags.get(documentId) ?? [] });
      });
      if (normalizedPatch.add.length > 0) {
        setTagOptions((currentOptions) =>
          isSameStringArray(currentOptions, previousTagOptions)
            ? currentOptions
            : previousTagOptions,
        );
      }
      notifyToast({
        title: "Unable to update tags",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
      void refreshSnapshot();
    } finally {
      targets.forEach((documentId) => clearRowPending(documentId, "tags"));
      setIsBulkTagSubmitting(false);
    }
  }, [
    applyDocumentUpdate,
    bulkTagAdd,
    bulkTagRemove,
    bulkTagTargets,
    clearRowPending,
    documentsById,
    markRowPending,
    notifyToast,
    onBulkTagCancel,
    queryClient,
    refreshSnapshot,
    tagOptions,
    updateRow,
    workspaceId,
  ]);

  const onBulkDeleteRequest = useCallback((selected: DocumentRow[]) => {
    const targets = selected.filter((document) => Boolean(document.id));
    if (targets.length === 0) return;
    setBulkDeleteTargets(targets);
  }, []);

  const onBulkDeleteCancel = useCallback(() => {
    if (isBulkDeleteSubmitting) return;
    setBulkDeleteTargets([]);
  }, [isBulkDeleteSubmitting]);

  const onBulkDeleteConfirm = useCallback(async () => {
    const targets = uniqueDocumentIds(bulkDeleteTargets);
    if (targets.length === 0) {
      onBulkDeleteCancel();
      return;
    }

    targets.forEach((documentId) => markRowPending(documentId, "delete"));
    setIsBulkDeleteSubmitting(true);
    try {
      const deletedIds = await deleteWorkspaceDocumentsBatch(workspaceId, targets);
      const resolvedDeletedIds = deletedIds.length > 0 ? deletedIds : targets;
      resolvedDeletedIds.forEach((documentId) => removeRow(documentId));
      void refreshSnapshot();
      notifyToast({
        title: "Documents deleted",
        description: `${resolvedDeletedIds.length} document${resolvedDeletedIds.length === 1 ? "" : "s"} deleted.`,
        intent: "success",
      });
      setSelectionResetToken((value) => value + 1);
      onBulkDeleteCancel();
    } catch (error) {
      notifyToast({
        title: "Unable to delete documents",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
      void refreshSnapshot();
    } finally {
      targets.forEach((documentId) => clearRowPending(documentId, "delete"));
      setIsBulkDeleteSubmitting(false);
    }
  }, [
    bulkDeleteTargets,
    clearRowPending,
    markRowPending,
    notifyToast,
    onBulkDeleteCancel,
    refreshSnapshot,
    removeRow,
    workspaceId,
  ]);

  const onBulkRestoreRequest = useCallback((selected: DocumentRow[]) => {
    const targets = selected.filter((document) => Boolean(document.id));
    if (targets.length === 0) return;
    setBulkRestoreTargets(targets);
  }, []);

  const onBulkRestoreCancel = useCallback(() => {
    if (isBulkRestoreSubmitting) return;
    setBulkRestoreTargets([]);
  }, [isBulkRestoreSubmitting]);

  const onBulkRestoreConfirm = useCallback(async () => {
    const targets = uniqueDocumentIds(bulkRestoreTargets);
    if (targets.length === 0) {
      onBulkRestoreCancel();
      return;
    }

    targets.forEach((documentId) => markRowPending(documentId, "restore"));
    setIsBulkRestoreSubmitting(true);
    try {
      const result = await restoreWorkspaceDocumentsBatch(workspaceId, targets);
      const restoredIds = result.restoredIds ?? [];
      const conflictCount = result.conflicts?.length ?? 0;
      const notFoundCount = result.notFoundIds?.length ?? 0;

      restoredIds.forEach((documentId) => removeRow(documentId));
      void refreshSnapshot();

      const summaryParts: string[] = [];
      if (restoredIds.length > 0) {
        summaryParts.push(`${restoredIds.length} restored`);
      }
      if (conflictCount > 0) {
        summaryParts.push(`${conflictCount} need rename`);
      }
      if (notFoundCount > 0) {
        summaryParts.push(`${notFoundCount} not found`);
      }

      notifyToast({
        title: "Batch restore complete",
        description: summaryParts.length > 0 ? summaryParts.join(", ") : "No documents were restored.",
        intent: conflictCount > 0 || notFoundCount > 0 ? "warning" : "success",
      });
      if (restoredIds.length > 0) {
        setSelectionResetToken((value) => value + 1);
      }
      onBulkRestoreCancel();
    } catch (error) {
      notifyToast({
        title: "Unable to restore documents",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
      void refreshSnapshot();
    } finally {
      targets.forEach((documentId) => clearRowPending(documentId, "restore"));
      setIsBulkRestoreSubmitting(false);
    }
  }, [
    bulkRestoreTargets,
    clearRowPending,
    markRowPending,
    notifyToast,
    onBulkRestoreCancel,
    refreshSnapshot,
    removeRow,
    workspaceId,
  ]);

  const onReprocessCancel = useCallback(() => {
    if (isReprocessSubmitting) return;
    setReprocessTargets([]);
  }, [isReprocessSubmitting]);

  const onReprocessConfirm = useCallback(
    async (runOptions: Pick<RunStreamOptions, "active_sheet_only" | "input_sheet_names">) => {
      if (reprocessTargets.length === 0) return;

      const requestedCount = reprocessTargets.length;
      const targets = [...reprocessTargets];
      targets.forEach((target) => markRowPending(target.id, "run"));
      setIsReprocessSubmitting(true);
      try {
        if (requestedCount === 1) {
          const target = targets[0]!;
          await createRun(workspaceId, {
            input_document_id: target.id,
            active_sheet_only: runOptions.active_sheet_only,
            input_sheet_names: runOptions.input_sheet_names,
          });
          notifyToast({
            title: "Reprocess queued",
            description: `${target.name} was queued for processing.`,
            intent: "success",
          });
        } else {
          const runs = await createRunsBatch(
            workspaceId,
            targets.map((target) => target.id),
            {
              active_sheet_only: runOptions.active_sheet_only,
            },
          );
          const queuedCount = runs.length;
          const skippedCount = Math.max(0, requestedCount - queuedCount);
          const summaryParts = [`${queuedCount} queued`];
          if (skippedCount > 0) summaryParts.push(`${skippedCount} skipped`);
          notifyToast({
            title: "Reprocess queued",
            description: summaryParts.join(", "),
            intent: "success",
          });
        }

        setSelectionResetToken((value) => value + 1);
        setReprocessTargets([]);
      } catch (error) {
        notifyToast({
          title: "Unable to reprocess documents",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
        void refreshSnapshot();
      } finally {
        targets.forEach((target) => clearRowPending(target.id, "run"));
        setIsReprocessSubmitting(false);
      }
    },
    [
      clearRowPending,
      markRowPending,
      notifyToast,
      refreshSnapshot,
      reprocessTargets,
      workspaceId,
    ],
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
      const snapshot = current.assignee ?? null;
      const shouldApplyOptimistic =
        assigneeId === null || (Boolean(person?.email) && Boolean(person?.label));
      const optimisticAssignee =
        assigneeId === null
          ? null
          : shouldApplyOptimistic && person?.email
            ? { id: assigneeId, name: person.label, email: person.email }
            : null;

      markRowPending(documentId, "assign");
      if (shouldApplyOptimistic) {
        updateRow(documentId, { assignee: optimisticAssignee });
      }
      try {
        const updated = await patchWorkspaceDocument(
          workspaceId,
          documentId,
          { assigneeId },
        );
        applyDocumentUpdate(documentId, updated);
      } catch (error) {
        if (shouldApplyOptimistic) {
          updateRow(documentId, { assignee: snapshot });
        }
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
      const normalizedTag = tag.trim();
      const normalizedTagKey = tagKey(normalizedTag);
      if (!normalizedTagKey) return;

      const tags = current.tags ?? [];
      const existingTag = tags.find((value) => tagKey(value) === normalizedTagKey);
      const hasTag = Boolean(existingTag);
      const nextTags = hasTag
        ? tags.filter((value) => tagKey(value) !== normalizedTagKey)
        : [...tags, normalizedTag];
      const isNewOption = !hasTag && !hasTagOption(tagOptions, normalizedTag);

      markRowPending(documentId, "tags");
      updateRow(documentId, { tags: nextTags });
      if (isNewOption) {
        setTagOptions((currentOptions) => {
          const merged = mergeTagOptions(currentOptions, [normalizedTag]);
          return isSameStringArray(merged, currentOptions) ? currentOptions : merged;
        });
      }
      try {
        const updated = await patchDocumentTags(
          workspaceId,
          documentId,
          hasTag ? { remove: [existingTag ?? normalizedTag] } : { add: [normalizedTag] },
          undefined,
        );
        applyDocumentUpdate(documentId, updated);
        if (isNewOption) {
          queryClient.setQueryData<TagCatalogPage | undefined>(
            ["documents-tags", workspaceId],
            (currentCatalog) => {
              if (!currentCatalog) return currentCatalog;
              const exists = currentCatalog.items.some((item) => tagKey(item.tag) === normalizedTagKey);
              if (exists) return currentCatalog;
              return {
                ...currentCatalog,
                items: [...currentCatalog.items, { tag: normalizedTag, document_count: 1 }],
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

  const onRenameInline = useCallback(
    async (document: DocumentRow, nextName: string) => {
      const current = documentsById[document.id] ?? document;
      markRowPending(current.id, "rename");
      try {
        const result = await renameMutation.renameDocument({
          documentId: current.id,
          currentName: current.name,
          nextName,
        });
        if (result) {
          notifyToast({
            title: "Document renamed.",
            intent: "success",
            duration: 2500,
          });
        }
      } catch (error) {
        const description = getRenameDocumentErrorMessage(error);
        notifyToast({
          title: "Unable to rename document",
          description,
          intent: "danger",
        });
        throw new Error(description);
      } finally {
        clearRowPending(current.id, "rename");
      }
    },
    [clearRowPending, documentsById, markRowPending, notifyToast, renameMutation],
  );
  const requestInlineRename = useCallback((documentId: string) => {
    inlineRenameNonceRef.current += 1;
    setInlineRenameRequest({
      documentId,
      nonce: inlineRenameNonceRef.current,
    });
  }, []);

  const onDeleteRequest = useCallback((document: DocumentRow) => {
    setDeleteTarget(document);
  }, []);

  const onDeleteCancel = useCallback(() => {
    setDeleteTarget(null);
  }, []);

  const onDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    markRowPending(deleteTarget.id, "delete");
    try {
      await deleteWorkspaceDocument(workspaceId, deleteTarget.id);
      removeRow(deleteTarget.id);
      void refreshSnapshot();
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
  }, [clearRowPending, deleteTarget, markRowPending, notifyToast, refreshSnapshot, removeRow, workspaceId]);

  const onRestoreRequest = useCallback((document: DocumentRow) => {
    setRestoreTarget(document);
    setRestoreRenameTarget(null);
    setRestoreRenameInitialName("");
    setRestoreRenameError(null);
  }, []);

  const onRestoreCancel = useCallback(() => {
    setRestoreTarget(null);
  }, []);

  const onRestoreRenameCancel = useCallback(() => {
    setRestoreRenameTarget(null);
    setRestoreRenameInitialName("");
    setRestoreRenameError(null);
  }, []);

  const onRestoreConfirm = useCallback(async () => {
    if (!restoreTarget) return;
    const current = documentsById[restoreTarget.id] ?? restoreTarget;
    markRowPending(current.id, "restore");
    try {
      await restoreWorkspaceDocument(workspaceId, current.id);
      removeRow(current.id);
      void refreshSnapshot();
      notifyToast({ title: "Document restored.", intent: "success", duration: 4000 });
      setRestoreTarget(null);
      onRestoreRenameCancel();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const restoreConflict = extractRestoreConflict(error);
        setRestoreTarget(null);
        setRestoreRenameTarget(current);
        setRestoreRenameInitialName(restoreConflict.suggestedName ?? current.name);
        setRestoreRenameError(null);
        return;
      }
      notifyToast({
        title: error instanceof Error ? error.message : "Unable to restore document.",
        intent: "danger",
      });
    } finally {
      clearRowPending(current.id, "restore");
    }
  }, [
    clearRowPending,
    documentsById,
    markRowPending,
    notifyToast,
    onRestoreRenameCancel,
    refreshSnapshot,
    removeRow,
    restoreTarget,
    workspaceId,
  ]);

  const onRestoreRenameConfirm = useCallback(async (nextName: string) => {
    if (!restoreRenameTarget) return;
    const current = documentsById[restoreRenameTarget.id] ?? restoreRenameTarget;
    markRowPending(current.id, "restore");
    setRestoreRenameError(null);
    try {
      await restoreWorkspaceDocument(workspaceId, current.id, { name: nextName });
      removeRow(current.id);
      void refreshSnapshot();
      notifyToast({ title: "Document restored.", intent: "success", duration: 4000 });
      onRestoreRenameCancel();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const restoreConflict = extractRestoreConflict(error);
        setRestoreRenameError(restoreConflict.message);
        if (restoreConflict.suggestedName) {
          setRestoreRenameInitialName(restoreConflict.suggestedName);
        }
        return;
      }
      const description = error instanceof Error ? error.message : "Unable to restore document.";
      setRestoreRenameError(description);
      notifyToast({
        title: "Unable to restore document",
        description,
        intent: "danger",
      });
    } finally {
      clearRowPending(current.id, "restore");
    }
  }, [
    clearRowPending,
    documentsById,
    markRowPending,
    notifyToast,
    onRestoreRenameCancel,
    refreshSnapshot,
    removeRow,
    restoreRenameTarget,
    workspaceId,
  ]);

  const markStale = useCallback(() => {
    if (page > 1) {
      setUpdatesAvailable(true);
    }
  }, [page]);

  const applyChangeEntries = useCallback(
    async (changes: DocumentChangeNotification[]) => {
      if (!changes.length) return;
      let needsRefresh = false;
      const { deleteIds, upsertIds } = partitionDocumentChanges(changes);

      if (deleteIds.length > 0) {
        deleteIds.forEach((documentId) => {
          if (documentsById[documentId]) {
            removeRow(documentId);
            if (page === 1) {
              needsRefresh = true;
            } else {
              markStale();
            }
          }
        });
      }

      if (upsertIds.length === 0) return;

      const rows = await fetchWorkspaceDocumentRowsByIdFilter(
        workspaceId,
        upsertIds,
        {
          sort,
          lifecycle,
          filters,
          joinOperator: joinOperator ?? undefined,
          q,
        },
      );
      const rowsById = new Map(rows.map((row) => [row.id, row]));

      upsertIds.forEach((documentId) => {
        const row = rowsById.get(documentId);
        const isVisible = Boolean(documentsById[documentId]);
        if (row) {
          if (isVisible) {
            updateRow(documentId, row);
          } else {
            if (page === 1) {
              needsRefresh = true;
            } else {
              markStale();
            }
          }
          return;
        }
        if (isVisible) {
          removeRow(documentId);
          if (page === 1) {
            needsRefresh = true;
          } else {
            markStale();
          }
        }
      });

      if (needsRefresh && page === 1) {
        await refreshSnapshot();
      }
    },
    [
      documentsById,
      filters,
      joinOperator,
      markStale,
      page,
      q,
      lifecycle,
      refreshSnapshot,
      removeRow,
      sort,
      updateRow,
      workspaceId,
    ],
  );

  useDocumentsDeltaSync({
    workspaceId,
    changesCursor,
    resetKey: viewKey,
    onApplyChanges: applyChangeEntries,
    onSnapshotStale: () => {
      void refreshSnapshot();
    },
  });

  const columns = useDocumentsColumns({
    lifecycle,
    people,
    currentUserId: currentUser.id,
    tagOptions,
    rowPresence,
    onOpenPreview: (documentId) => openDocument(documentId, "preview"),
    onOpenActivity: (documentId) =>
      openDocument(documentId, "activity", { activityFilter: "comments" }),
    onAssign,
    onToggleTag,
    onTagOptionsChange: handleTagOptionsChange,
    onRenameInline,
    onDeleteRequest,
    onRestoreRequest,
    onReprocessRequest,
    onCancelRunRequest,
    onDownloadLatest: handleDownloadLatest,
    onDownloadOriginal: handleDownloadOriginal,
    isRowActionPending: isRowMutationPending,
    inlineRenameRequest,
  });

  const { table, debounceMs, throttleMs, shallow } = useDataTable({
    data: documents,
    columns,
    pageCount,
    enableColumnResizing: true,
    defaultColumn: {
      size: 140,
      minSize: 90,
    },
    initialState: {
      sorting: DEFAULT_SORTING,
      pagination: { pageIndex: 0, pageSize: DEFAULT_PAGE_SIZE },
      columnVisibility: {
        select: true,
        id: false,
        fileType: false,
        uploaderId: false,
        byteSize: false,
        activityAt: false,
        deletedAt: false,
        lastRunPhase: true,
        lastRunAt: true,
      },
      columnPinning: { left: ["select"] },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  const documentViews = useDocumentViews({
    workspaceId,
    userId: currentUser.id,
    table,
    canManagePublicViews,
  });

  const hasDocuments = documents.length > 0;
  const showInitialLoading = isLoading && !hasDocuments;
  const showInitialError = Boolean(error) && !hasDocuments;
  const handleUpdatesRefresh = useCallback(() => {
    setUpdatesAvailable(false);
    void refreshSnapshot();
  }, [refreshSnapshot]);

  const openSaveAsDialog = useCallback((sourceView?: DocumentViewRecord | null) => {
    const defaultName = sourceView
      ? `${sourceView.name} copy`
      : documentViews.selectedView
        ? `${documentViews.selectedView.name} copy`
        : "New view";
    setSaveAsName(defaultName);
    setSaveAsVisibility("private");
    setSaveAsError(null);
    setSaveAsOpen(true);
  }, [documentViews.selectedView]);

  const closeSaveAsDialog = useCallback(() => {
    if (documentViews.isCreating) return;
    setSaveAsOpen(false);
    setSaveAsError(null);
  }, [documentViews.isCreating]);

  const handleSaveSelectedView = useCallback(async () => {
    try {
      await documentViews.saveSelectedView();
      notifyToast({
        title: "View updated",
        description: "Saved changes to this view.",
        intent: "success",
      });
    } catch (error) {
      notifyToast({
        title: "Unable to save view",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
    }
  }, [documentViews, notifyToast]);

  const handleDiscardViewChanges = useCallback(async () => {
    try {
      await documentViews.discardChanges();
    } catch (error) {
      notifyToast({
        title: "Unable to discard changes",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
    }
  }, [documentViews, notifyToast]);

  const handleSaveAsNewView = useCallback(async () => {
    const nextName = saveAsName.trim();
    if (!nextName) {
      setSaveAsError("Name is required.");
      return;
    }
    if (saveAsVisibility === "public" && !canManagePublicViews) {
      setSaveAsError("Public views require additional permissions.");
      return;
    }
    try {
      await documentViews.saveAsNewView({
        name: nextName,
        visibility: saveAsVisibility,
      });
      setSaveAsOpen(false);
      setSaveAsError(null);
      notifyToast({
        title: "View created",
        description: `${nextName} is now available in your views list.`,
        intent: "success",
      });
    } catch (error) {
      setSaveAsError(error instanceof Error ? error.message : "Unable to create view.");
    }
  }, [canManagePublicViews, documentViews, notifyToast, saveAsName, saveAsVisibility]);

  const openRenameViewDialog = useCallback(
    (view: DocumentViewRecord) => {
      if (!documentViews.canMutateView(view)) return;
      setViewRenameTarget(view);
      setViewRenameName(view.name);
      setViewRenameError(null);
    },
    [documentViews],
  );

  const closeRenameViewDialog = useCallback(() => {
    if (isViewRenameSubmitting) return;
    setViewRenameTarget(null);
    setViewRenameName("");
    setViewRenameError(null);
  }, [isViewRenameSubmitting]);

  const handleRenameViewConfirm = useCallback(async () => {
    if (!viewRenameTarget) return;
    const nextName = viewRenameName.trim();
    if (!nextName) {
      setViewRenameError("Name is required.");
      return;
    }
    setIsViewRenameSubmitting(true);
    try {
      await updateSavedDocumentView(workspaceId, viewRenameTarget.id, { name: nextName });
      await queryClient.invalidateQueries({ queryKey: ["document-views", workspaceId] });
      setViewRenameTarget(null);
      setViewRenameName("");
      setViewRenameError(null);
      notifyToast({
        title: "View renamed",
        description: `Renamed to ${nextName}.`,
        intent: "success",
      });
    } catch (error) {
      setViewRenameError(error instanceof Error ? error.message : "Unable to rename view.");
    } finally {
      setIsViewRenameSubmitting(false);
    }
  }, [notifyToast, queryClient, viewRenameName, viewRenameTarget, workspaceId]);

  const openDeleteViewDialog = useCallback(
    (view: DocumentViewRecord) => {
      if (!documentViews.canMutateView(view)) return;
      setViewDeleteTarget(view);
    },
    [documentViews],
  );

  const closeDeleteViewDialog = useCallback(() => {
    if (isViewDeleteSubmitting) return;
    setViewDeleteTarget(null);
  }, [isViewDeleteSubmitting]);

  const handleDeleteViewConfirm = useCallback(async () => {
    if (!viewDeleteTarget) return;
    setIsViewDeleteSubmitting(true);
    try {
      await documentViews.removeView(viewDeleteTarget);
      notifyToast({
        title: "View deleted",
        description: `${viewDeleteTarget.name} was removed.`,
        intent: "success",
      });
      setViewDeleteTarget(null);
    } catch (error) {
      notifyToast({
        title: "Unable to delete view",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
    } finally {
      setIsViewDeleteSubmitting(false);
    }
  }, [documentViews, notifyToast, viewDeleteTarget]);

  const handleDuplicateView = useCallback(
    async (view: DocumentViewRecord) => {
      if (!documentViews.canMutateView(view)) return;
      const name = `${view.name} copy`;
      const visibility: "private" | "public" =
        view.visibility === "public" && canManagePublicViews ? "public" : "private";
      try {
        const created = await createSavedDocumentView(workspaceId, {
          name,
          visibility,
          queryState: view.queryState,
          tableState: view.tableState ?? undefined,
        });
        await queryClient.invalidateQueries({ queryKey: ["document-views", workspaceId] });
        await documentViews.selectView(created);
        notifyToast({
          title: "View duplicated",
          description: `${name} is now available in your views list.`,
          intent: "success",
        });
      } catch (error) {
        notifyToast({
          title: "Unable to duplicate view",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      }
    },
    [canManagePublicViews, documentViews, notifyToast, queryClient, workspaceId],
  );
  const buildRowContextMenuItems = useCallback(
    (document: DocumentRow) => {
      const row = documentsById[document.id] ?? document;
      const actions = buildDocumentRowActions({
        document: row,
        lifecycle,
        isBusy: isRowMutationPending(row.id),
        isSelfAssigned: row.assignee?.id === currentUser.id,
        canRenameInline: lifecycle === "active",
        surface: "context",
        onOpen: () => openDocument(row.id, "activity"),
        onOpenPreview: () => openDocument(row.id, "preview"),
        onDownloadLatest: handleDownloadLatest,
        onDownloadOriginal: handleDownloadOriginal,
        onAssignToMe:
          lifecycle === "active"
            ? () => {
                void onAssign(row.id, currentUser.id);
              }
            : undefined,
        onRename:
          lifecycle === "active"
            ? () => {
                requestInlineRename(row.id);
              }
            : undefined,
        onDeleteRequest: lifecycle === "active" ? onDeleteRequest : undefined,
      });
      return toContextMenuItems(actions);
    },
    [
      currentUser.id,
      documentsById,
      handleDownloadLatest,
      handleDownloadOriginal,
      isRowMutationPending,
      lifecycle,
      onAssign,
      onDeleteRequest,
      openDocument,
      requestInlineRename,
    ],
  );

  const viewsToolbarControl = (
    <DocumentsViewsDropdown
      systemViews={documentViews.systemViews}
      publicViews={documentViews.publicViews}
      privateViews={documentViews.privateViews}
      selectedViewId={documentViews.selectedViewId}
      hasExplicitListState={documentViews.hasExplicitListState}
      isEdited={documentViews.isEdited}
      isLoading={documentViews.isLoading}
      isFetching={documentViews.isFetching}
      isSaving={documentViews.isSaving}
      isCreating={documentViews.isCreating}
      isDeleting={documentViews.isDeleting}
      canMutateSelectedView={documentViews.canMutateSelectedView}
      canMutateView={documentViews.canMutateView}
      onSelectView={documentViews.selectView}
      onCreateView={() => openSaveAsDialog(null)}
      onSaveSelectedView={() => {
        void handleSaveSelectedView();
      }}
      onDiscardViewChanges={() => {
        void handleDiscardViewChanges();
      }}
      onRenameView={openRenameViewDialog}
      onDuplicateView={(view) => {
        void handleDuplicateView(view);
      }}
      onDeleteView={openDeleteViewDialog}
    />
  );

  const toolbarContent = (
    <DocumentsToolbar
      configMissing={configMissing}
      processingPaused={processingPaused}
      hasDocuments={hasDocuments}
      isListFetching={isFetching}
      hasListError={Boolean(error)}
      toolbarActions={toolbarActions}
    />
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
  const showUpdatesBanner = updatesAvailable && page > 1;
  const updatesBanner = showUpdatesBanner ? (
    <div className="mb-3 flex items-center justify-between rounded-lg border border-muted bg-muted/40 px-3 py-2 text-sm">
      <span>Updates are available for this view.</span>
      <Button variant="ghost" size="sm" onClick={handleUpdatesRefresh}>
        Refresh
      </Button>
    </div>
  ) : null;

  const deletePending =
    deleteTarget ? pendingMutations[deleteTarget.id]?.has("delete") ?? false : false;
  const restorePending =
    restoreTarget ? pendingMutations[restoreTarget.id]?.has("restore") ?? false : false;
  const restoreRenamePending =
    restoreRenameTarget ? pendingMutations[restoreRenameTarget.id]?.has("restore") ?? false : false;
  const bulkAssignCount = bulkAssignTargets.length;
  const bulkTagCount = bulkTagTargets.length;
  const bulkDeleteCount = bulkDeleteTargets.length;
  const bulkRestoreCount = bulkRestoreTargets.length;
  const normalizedBulkTagPatch = normalizeBulkTagPatch({
    add: bulkTagAdd,
    remove: bulkTagRemove,
  });
  const canApplyBulkTags =
    normalizedBulkTagPatch.add.length > 0 || normalizedBulkTagPatch.remove.length > 0;
  const bulkDeletePreview =
    bulkDeleteTargets.length === 0
      ? []
      : bulkDeleteTargets.slice(0, 3).map((document) => document.name);
  const bulkRestorePreview =
    bulkRestoreTargets.length === 0
      ? []
      : bulkRestoreTargets.slice(0, 3).map((document) => document.name);

  const tableContent = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col px-3 pb-4 pt-2 sm:px-4 sm:pb-6 lg:px-6">
        {configBanner}
        {updatesBanner}
        <DocumentsTable
          table={table}
          debounceMs={debounceMs}
          throttleMs={throttleMs}
          shallow={shallow}
          rowPresence={rowPresence}
          leadingToolbarActions={viewsToolbarControl}
          toolbarActions={toolbarContent}
          onRowActivate={(document) => openDocument(document.id, "activity")}
          onBulkReprocessRequest={lifecycle === "active" ? onBulkReprocessRequest : undefined}
          onBulkCancelRequest={lifecycle === "active" ? onBulkCancelRequest : undefined}
          onBulkAssignRequest={lifecycle === "active" ? onBulkAssignRequest : undefined}
          onBulkTagRequest={lifecycle === "active" ? onBulkTagRequest : undefined}
          onBulkDeleteRequest={lifecycle === "active" ? onBulkDeleteRequest : undefined}
          onBulkRestoreRequest={lifecycle === "deleted" ? onBulkRestoreRequest : undefined}
          onBulkDownloadRequest={lifecycle === "active" ? onBulkDownloadRequest : undefined}
          onBulkDownloadOriginalRequest={lifecycle === "active" ? onBulkDownloadOriginalRequest : undefined}
          buildRowContextMenuItems={buildRowContextMenuItems}
          selectionResetToken={selectionResetToken}
        />
      </div>
    </div>
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        {tableContent}
      </div>
      <Dialog
        open={bulkAssignCount > 0}
        onOpenChange={(open) => (!open ? onBulkAssignCancel() : undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign selected documents</DialogTitle>
            <DialogDescription>
              {bulkAssignCount} document{bulkAssignCount === 1 ? "" : "s"} selected.
              Choose who should own them.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Assign to
            </p>
            <Select
              value={bulkAssignChoice || undefined}
              onValueChange={setBulkAssignChoice}
              disabled={isBulkAssignSubmitting}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a person..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ASSIGN_CHOICE_UNASSIGN}>Unassigned</SelectItem>
                {people.map((person) => (
                  <SelectItem key={person.id} value={person.id}>
                    {person.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={onBulkAssignCancel} disabled={isBulkAssignSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={onBulkAssignConfirm}
              disabled={isBulkAssignSubmitting || !bulkAssignChoice}
            >
              {isBulkAssignSubmitting ? "Updating..." : "Apply assignment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={bulkTagCount > 0}
        onOpenChange={(open) => (!open ? onBulkTagCancel() : undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit tags for selected documents</DialogTitle>
            <DialogDescription>
              Apply tag changes to {bulkTagCount} document{bulkTagCount === 1 ? "" : "s"}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Add tags
              </p>
              <TagSelector
                value={bulkTagAdd}
                onValueChange={(next) => {
                  const normalized = mergeTagOptions(next, []);
                  const normalizedKeys = new Set(normalized.map(tagKey));
                  setBulkTagAdd(normalized);
                  setBulkTagRemove((current) =>
                    current.filter((tag) => !normalizedKeys.has(tagKey(tag))),
                  );
                }}
                options={tagOptions}
                onOptionsChange={handleTagOptionsChange}
                disabled={isBulkTagSubmitting}
                allowCreate
                placeholder={bulkTagAdd.length ? "Search tags..." : "Search or create tags..."}
                emptyText={(query) => (query ? "No matches." : "No tags yet.")}
              >
                <Button variant="outline" className="w-full justify-start" disabled={isBulkTagSubmitting}>
                  {bulkTagAdd.length > 0
                    ? `${bulkTagAdd.length} tag${bulkTagAdd.length === 1 ? "" : "s"} selected`
                    : "Select tags to add"}
                </Button>
              </TagSelector>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Remove tags
              </p>
              <TagSelector
                value={bulkTagRemove}
                onValueChange={(next) => {
                  const normalized = mergeTagOptions(next, []);
                  const normalizedKeys = new Set(normalized.map(tagKey));
                  setBulkTagRemove(normalized);
                  setBulkTagAdd((current) =>
                    current.filter((tag) => !normalizedKeys.has(tagKey(tag))),
                  );
                }}
                options={tagOptions}
                disabled={isBulkTagSubmitting}
                allowCreate={false}
                placeholder={bulkTagRemove.length ? "Search tags..." : "Select tags to remove..."}
                emptyText={(query) => (query ? "No matches." : "No tags yet.")}
              >
                <Button variant="outline" className="w-full justify-start" disabled={isBulkTagSubmitting}>
                  {bulkTagRemove.length > 0
                    ? `${bulkTagRemove.length} tag${bulkTagRemove.length === 1 ? "" : "s"} selected`
                    : "Select tags to remove"}
                </Button>
              </TagSelector>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={onBulkTagCancel} disabled={isBulkTagSubmitting}>
              Cancel
            </Button>
            <Button onClick={onBulkTagConfirm} disabled={isBulkTagSubmitting || !canApplyBulkTags}>
              {isBulkTagSubmitting ? "Updating..." : "Apply tag changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={bulkDeleteCount > 0}
        onOpenChange={(open) => (!open ? onBulkDeleteCancel() : undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete selected documents?</DialogTitle>
            <DialogDescription>
              Move {bulkDeleteCount} document{bulkDeleteCount === 1 ? "" : "s"} to Deleted.
              You can restore these later from the Deleted view.
            </DialogDescription>
          </DialogHeader>
          {bulkDeletePreview.length > 0 ? (
            <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
              <p className="mb-1 font-medium">Selected:</p>
              <ul className="list-disc pl-4 text-muted-foreground">
                {bulkDeletePreview.map((name, index) => (
                  <li key={`${name}-${index}`}>{name}</li>
                ))}
              </ul>
              {bulkDeleteCount > bulkDeletePreview.length ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  +{bulkDeleteCount - bulkDeletePreview.length} more
                </p>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={onBulkDeleteCancel} disabled={isBulkDeleteSubmitting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={onBulkDeleteConfirm}
              disabled={isBulkDeleteSubmitting}
            >
              {isBulkDeleteSubmitting ? "Deleting..." : "Delete selected"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={bulkRestoreCount > 0}
        onOpenChange={(open) => (!open ? onBulkRestoreCancel() : undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore selected documents?</DialogTitle>
            <DialogDescription>
              Restore {bulkRestoreCount} document{bulkRestoreCount === 1 ? "" : "s"} to the active list.
            </DialogDescription>
          </DialogHeader>
          {bulkRestorePreview.length > 0 ? (
            <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
              <p className="mb-1 font-medium">Selected:</p>
              <ul className="list-disc pl-4 text-muted-foreground">
                {bulkRestorePreview.map((name, index) => (
                  <li key={`${name}-${index}`}>{name}</li>
                ))}
              </ul>
              {bulkRestoreCount > bulkRestorePreview.length ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  +{bulkRestoreCount - bulkRestorePreview.length} more
                </p>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={onBulkRestoreCancel} disabled={isBulkRestoreSubmitting}>
              Cancel
            </Button>
            <Button
              variant="secondary"
              onClick={onBulkRestoreConfirm}
              disabled={isBulkRestoreSubmitting}
            >
              {isBulkRestoreSubmitting ? "Restoring..." : "Restore selected"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <DocumentsDialogs
        saveAsOpen={saveAsOpen}
        onSaveAsOpenChange={(open) => {
          if (!open) {
            closeSaveAsDialog();
            return;
          }
          setSaveAsOpen(true);
        }}
        saveAsName={saveAsName}
        onSaveAsNameChange={(value) => {
          setSaveAsName(value);
          if (saveAsError) setSaveAsError(null);
        }}
        saveAsVisibility={saveAsVisibility}
        onSaveAsVisibilityChange={setSaveAsVisibility}
        saveAsError={saveAsError}
        canManagePublicViews={canManagePublicViews}
        isCreatingView={documentViews.isCreating}
        onCloseSaveAs={closeSaveAsDialog}
        onSaveAsNewView={() => {
          void handleSaveAsNewView();
        }}
        viewRenameTarget={viewRenameTarget}
        viewRenameName={viewRenameName}
        onViewRenameNameChange={(value) => {
          setViewRenameName(value);
          if (viewRenameError) setViewRenameError(null);
        }}
        viewRenameError={viewRenameError}
        isViewRenameSubmitting={isViewRenameSubmitting}
        onCloseRenameView={closeRenameViewDialog}
        onConfirmRenameView={() => {
          void handleRenameViewConfirm();
        }}
        viewDeleteTarget={viewDeleteTarget}
        isViewDeleteSubmitting={isViewDeleteSubmitting}
        onCloseDeleteView={closeDeleteViewDialog}
        onConfirmDeleteView={() => {
          void handleDeleteViewConfirm();
        }}
      />
      <RenameDocumentDialog
        open={Boolean(restoreRenameTarget)}
        documentName={restoreRenameInitialName || restoreRenameTarget?.name || ""}
        isPending={restoreRenamePending}
        errorMessage={restoreRenameError}
        onOpenChange={(open) => {
          if (!open) onRestoreRenameCancel();
        }}
        onClearError={() => {
          if (restoreRenameError) setRestoreRenameError(null);
        }}
        onSubmit={onRestoreRenameConfirm}
      />
      <ReprocessPreflightDialog
        open={reprocessTargets.length > 0}
        workspaceId={workspaceId}
        documents={reprocessTargets}
        onConfirm={onReprocessConfirm}
        onCancel={onReprocessCancel}
        processingPaused={processingPaused}
        configMissing={configMissing}
        isSubmitting={isReprocessSubmitting}
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
                ? `Move "${deleteTarget.name}" to Deleted. You can restore it later from the Deleted view.`
                : "Move this document to Deleted. You can restore it later from the Deleted view."}
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
      <Dialog
        open={Boolean(restoreTarget)}
        onOpenChange={(open) => (!open ? onRestoreCancel() : undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore document?</DialogTitle>
            <DialogDescription>
              {restoreTarget
                ? `Restore "${restoreTarget.name}" to the active list.`
                : "Restore this document to the active list."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={onRestoreCancel} disabled={restorePending}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={onRestoreConfirm} disabled={restorePending}>
              {restorePending ? "Restoring..." : "Restore"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
