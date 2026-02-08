import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { parseAsStringEnum, useQueryState } from "nuqs";
import { useNavigate } from "react-router-dom";

import { resolveApiUrl } from "@/api/client";
import {
  deleteWorkspaceDocument,
  fetchWorkspaceDocumentRowsByIdFilter,
  patchWorkspaceDocument,
  type DocumentChangeNotification,
  type DocumentRecord,
  type DocumentUploadResponse,
} from "@/api/documents";
import { patchDocumentTags, fetchTagCatalog } from "@/api/documents/tags";
import { ApiError } from "@/api/errors";
import { cancelRun, createRun, createRunsBatch } from "@/api/runs/api";
import type { RunStreamOptions } from "@/api/runs/api";
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
import type { PresenceParticipant } from "@/types/presence";
import type { components } from "@/types";
import type { UploadManagerItem } from "@/pages/Workspace/sections/Documents/list/upload/useUploadManager";

import { DocumentsPresenceIndicator } from "../../shared/presence/DocumentsPresenceIndicator";
import { inferFileType, shortId } from "../../shared/utils";
import { partitionDocumentChanges } from "../../shared/documentChanges";
import type { DocumentRow, WorkspacePerson } from "../../shared/types";
import { useDocumentsListParams } from "../hooks/useDocumentsListParams";
import { useDocumentsView } from "../hooks/useDocumentsView";
import { useDocumentsDeltaSync } from "../../shared/hooks/useDocumentsDeltaSync";
import { getRenameDocumentErrorMessage, useRenameDocumentMutation } from "../../shared/hooks/useRenameDocumentMutation";
import { buildDocumentDetailUrl } from "../../shared/navigation";
import { RenameDocumentDialog } from "../../shared/ui/RenameDocumentDialog";
import { DocumentsConfigBanner } from "./DocumentsConfigBanner";
import { DocumentsEmptyState } from "./DocumentsEmptyState";
import { DocumentsTable } from "./DocumentsTable";
import { useDocumentsColumns } from "./documentsColumns";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
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

type RowMutation = "delete" | "assign" | "rename" | "tags" | "run";

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

function deriveFileType(name: string): DocumentRow["fileType"] {
  return inferFileType(name);
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
  const navigate = useNavigate();
  const [deleteTarget, setDeleteTarget] = useState<DocumentRow | null>(null);
  const [renameTarget, setRenameTarget] = useState<DocumentRow | null>(null);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [pendingMutations, setPendingMutations] = useState<Record<string, Set<RowMutation>>>({});
  const [reprocessTargets, setReprocessTargets] = useState<ReprocessTargetDocument[]>([]);
  const [isReprocessSubmitting, setIsReprocessSubmitting] = useState(false);
  const [selectionResetToken, setSelectionResetToken] = useState(0);
  const renameMutation = useRenameDocumentMutation({ workspaceId });

  const [filterFlag, setFilterFlag] = useQueryState(
    "filterFlag",
    parseAsStringEnum(["advancedFilters"]).withOptions({ clearOnDefault: true }),
  );
  const filterMode = filterFlag === "advancedFilters" ? "advanced" : "simple";
  const presence = useWorkspacePresence();
  const { page, perPage, sort, q, filters, joinOperator } = useDocumentsListParams({ filterMode });
  const filtersKey = useMemo(() => (filters?.length ? JSON.stringify(filters) : ""), [filters]);
  const viewKey = useMemo(
    () => [workspaceId, page, perPage, sort ?? "", q ?? "", filtersKey, joinOperator ?? ""].join("|"),
    [filtersKey, joinOperator, page, perPage, q, sort, workspaceId],
  );
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

  const onToggleFilterMode = useCallback(() => {
    setFilterFlag(filterFlag === "advancedFilters" ? null : "advancedFilters");
  }, [filterFlag, setFilterFlag]);

  const handledUploadsRef = useRef(new Set<string>());
  const completedUploadsRef = useRef(new Set<string>());

  useEffect(() => {
    setDeleteTarget(null);
    setRenameTarget(null);
    setRenameError(null);
    setPendingMutations({});
    setReprocessTargets([]);
    setIsReprocessSubmitting(false);
    setSelectionResetToken(0);
    setUpdatesAvailable(false);
    handledUploadsRef.current.clear();
    completedUploadsRef.current.clear();
  }, [workspaceId]);

  useEffect(() => {
    setUpdatesAvailable(false);
  }, [viewKey]);

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
      const url = resolveApiUrl(`/api/v1/workspaces/${workspaceId}/runs/${runId}/output/download`);
      openDownload(url);
    },
    [notifyToast, openDownload],
  );

  const handleDownloadLatest = useCallback(
    (document: DocumentRow) => {
      const url = resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`);
      openDownload(url);
    },
    [openDownload, workspaceId],
  );

  const handleDownloadVersion = useCallback(
    (document: DocumentRow, versionNo: number) => {
      const url = resolveApiUrl(
        `/api/v1/workspaces/${workspaceId}/documents/${document.id}/versions/${versionNo}/download`,
      );
      openDownload(url);
    },
    [openDownload, workspaceId],
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

  const onRenameRequest = useCallback((document: DocumentRow) => {
    setRenameTarget(document);
    setRenameError(null);
  }, []);

  const onRenameCancel = useCallback(() => {
    setRenameTarget(null);
    setRenameError(null);
    renameMutation.reset();
  }, [renameMutation]);

  const onRenameConfirm = useCallback(async (nextName: string) => {
    if (!renameTarget) return;
    const current = documentsById[renameTarget.id] ?? renameTarget;
    markRowPending(current.id, "rename");
    setRenameError(null);
    try {
      const result = await renameMutation.renameDocument({
        documentId: current.id,
        currentName: current.name,
        nextName,
      });
      if (!result) {
        onRenameCancel();
        return;
      }
      notifyToast({
        title: "Document renamed.",
        intent: "success",
        duration: 4000,
      });
      onRenameCancel();
    } catch (error) {
      const description = getRenameDocumentErrorMessage(error);
      setRenameError(description);
      notifyToast({
        title: "Unable to rename document",
        description,
        intent: "danger",
      });
    } finally {
      clearRowPending(current.id, "rename");
    }
  }, [
    clearRowPending,
    documentsById,
    markRowPending,
    notifyToast,
    onRenameCancel,
    renameMutation,
    renameTarget,
  ]);

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
    filterMode,
    people,
    tagOptions,
    rowPresence,
    onOpenDocument: (documentId) => openDocument(documentId, "activity"),
    onOpenPreview: (documentId) => openDocument(documentId, "preview"),
    onOpenActivity: (documentId) =>
      openDocument(documentId, "activity", { activityFilter: "comments" }),
    onAssign,
    onToggleTag,
    onTagOptionsChange: handleTagOptionsChange,
    onRenameRequest,
    onDeleteRequest,
    onReprocessRequest,
    onCancelRunRequest,
    onDownloadOutput: handleDownloadOutput,
    onDownloadLatest: handleDownloadLatest,
    onDownloadVersion: handleDownloadVersion,
    isRowActionPending: isRowMutationPending,
  });

  const hasDocuments = documents.length > 0;
  const showInitialLoading = isLoading && !hasDocuments;
  const showInitialError = Boolean(error) && !hasDocuments;
  const handleUpdatesRefresh = useCallback(() => {
    setUpdatesAvailable(false);
    void refreshSnapshot();
  }, [refreshSnapshot]);

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
  const renamePending =
    renameTarget ? pendingMutations[renameTarget.id]?.has("rename") ?? false : false;

  const tableContent = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col px-3 pb-4 pt-2 sm:px-4 sm:pb-6 lg:px-6">
        {configBanner}
        {updatesBanner}
        <DocumentsTable
          data={documents}
          pageCount={pageCount}
          columns={columns}
          filterMode={filterMode}
          onToggleFilterMode={onToggleFilterMode}
          toolbarActions={toolbarContent}
          onBulkReprocessRequest={onBulkReprocessRequest}
          onBulkCancelRequest={onBulkCancelRequest}
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
      <RenameDocumentDialog
        open={Boolean(renameTarget)}
        documentName={renameTarget?.name ?? ""}
        isPending={renamePending}
        errorMessage={renameError}
        onOpenChange={(open) => {
          if (!open) onRenameCancel();
        }}
        onClearError={() => {
          if (renameError) setRenameError(null);
        }}
        onSubmit={onRenameConfirm}
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
  return [...participants].sort((a, b) => {
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
