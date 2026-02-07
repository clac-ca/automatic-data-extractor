import { useCallback } from "react";
import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { patchWorkspaceDocument, type DocumentListRow, type DocumentPageResult, type DocumentRecord } from "@/api/documents";
import { ApiError } from "@/api/errors";

import { inferFileType } from "../utils";

const DUPLICATE_NAME_MESSAGE = "A document with this name already exists.";
const EXTENSION_LOCKED_MESSAGE = "File extension cannot be changed.";

type RenameDocumentInput = {
  documentId: string;
  currentName: string;
  nextName: string;
};

type RenameMutationContext = {
  listSnapshots: Array<[QueryKey, DocumentPageResult | undefined]>;
  detailSnapshot: DocumentListRow | undefined;
};

function buildOptimisticRowUpdate(nextName: string): Partial<DocumentListRow> {
  const timestamp = new Date().toISOString();
  return {
    name: nextName,
    fileType: inferFileType(nextName),
    updatedAt: timestamp,
    activityAt: timestamp,
  };
}

function buildServerRowUpdate(updated: DocumentRecord): Partial<DocumentListRow> {
  if (updated.listRow) {
    return updated.listRow;
  }
  return {
    name: updated.name,
    fileType: inferFileType(updated.name),
    updatedAt: updated.updatedAt,
    activityAt: updated.activityAt ?? updated.updatedAt,
    tags: updated.tags ?? [],
    assignee: updated.assignee ?? null,
    uploader: updated.uploader ?? null,
    lastRun: updated.lastRun ?? null,
    lastRunMetrics: updated.lastRunMetrics ?? null,
    lastRunTableColumns: updated.lastRunTableColumns ?? null,
    lastRunFields: updated.lastRunFields ?? null,
  };
}

function applyRowUpdateToPages(
  page: DocumentPageResult | undefined,
  documentId: string,
  updates: Partial<DocumentListRow>,
) {
  if (!page?.items?.length) return page;
  let changed = false;
  const items = page.items.map((item) => {
    if (item.id !== documentId) return item;
    changed = true;
    return { ...item, ...updates };
  });
  return changed ? { ...page, items } : page;
}

function applyRowUpdateToDetail(
  row: DocumentListRow | undefined,
  updates: Partial<DocumentListRow>,
) {
  if (!row) return row;
  return { ...row, ...updates };
}

export function getRenameDocumentErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return DUPLICATE_NAME_MESSAGE;
    if (error.status === 422) return EXTENSION_LOCKED_MESSAGE;
  }
  return error instanceof Error ? error.message : "Please try again.";
}

export function useRenameDocumentMutation({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();

  const mutation = useMutation<DocumentRecord, Error, RenameDocumentInput, RenameMutationContext>({
    mutationFn: ({ documentId, nextName }) =>
      patchWorkspaceDocument(workspaceId, documentId, { name: nextName }),
    onMutate: async ({ documentId, nextName }) => {
      const listQueryPrefix = ["documents", workspaceId] as const;
      const detailQueryKey = ["documents-detail", workspaceId, documentId] as const;

      await Promise.all([
        queryClient.cancelQueries({ queryKey: listQueryPrefix }),
        queryClient.cancelQueries({ queryKey: detailQueryKey }),
      ]);

      const listSnapshots = queryClient.getQueriesData<DocumentPageResult>({
        queryKey: listQueryPrefix,
      });
      const detailSnapshot = queryClient.getQueryData<DocumentListRow>(detailQueryKey);
      const optimisticUpdate = buildOptimisticRowUpdate(nextName);

      listSnapshots.forEach(([queryKey]) => {
        queryClient.setQueryData<DocumentPageResult | undefined>(queryKey, (current) =>
          applyRowUpdateToPages(current, documentId, optimisticUpdate),
        );
      });
      queryClient.setQueryData<DocumentListRow | undefined>(detailQueryKey, (current) =>
        applyRowUpdateToDetail(current, optimisticUpdate),
      );

      return { listSnapshots, detailSnapshot };
    },
    onError: (_error, variables, context) => {
      if (!context) return;
      context.listSnapshots.forEach(([queryKey, snapshot]) => {
        queryClient.setQueryData(queryKey, snapshot);
      });
      const detailQueryKey = ["documents-detail", workspaceId, variables.documentId] as const;
      queryClient.setQueryData(detailQueryKey, context.detailSnapshot);
    },
    onSuccess: (updated, variables) => {
      const listQueryPrefix = ["documents", workspaceId] as const;
      const detailQueryKey = ["documents-detail", workspaceId, variables.documentId] as const;
      const serverUpdate = buildServerRowUpdate(updated);

      queryClient.setQueriesData<DocumentPageResult>({ queryKey: listQueryPrefix }, (current) =>
        applyRowUpdateToPages(current, variables.documentId, serverUpdate),
      );
      queryClient.setQueryData<DocumentListRow | undefined>(detailQueryKey, (current) =>
        applyRowUpdateToDetail(current, serverUpdate),
      );
    },
  });

  const renameDocument = useCallback(
    async ({ documentId, currentName, nextName }: RenameDocumentInput) => {
      const normalized = nextName.trim();
      if (!normalized) {
        throw new Error("Document name cannot be blank.");
      }
      if (normalized === currentName) {
        return null;
      }
      return mutation.mutateAsync({ documentId, currentName, nextName: normalized });
    },
    [mutation],
  );

  const pendingDocumentId =
    mutation.isPending && mutation.variables ? mutation.variables.documentId : null;

  return {
    renameDocument,
    isRenaming: mutation.isPending,
    pendingDocumentId,
    reset: mutation.reset,
  };
}
