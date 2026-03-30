import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaceDocuments, type DocumentListRow, type DocumentPageResult } from "@/api/documents";
import type { DocumentLifecycle } from "@/api/documents";
import type { FilterItem, FilterJoinOperator } from "@/api/listing";

import type { DocumentRow } from "../../shared/types";

export function useDocumentsListData({
  workspaceId,
  page,
  perPage,
  sort,
  q,
  lifecycle,
  filters,
  joinOperator,
  enabled = true,
}: {
  workspaceId: string;
  page: number;
  perPage: number;
  sort: string | null;
  q: string | null;
  lifecycle: DocumentLifecycle;
  filters: FilterItem[] | null;
  joinOperator: FilterJoinOperator | null;
  enabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const [uploadProgressById, setUploadProgressById] = useState<Record<string, number | null>>({});

  useEffect(() => {
    setUploadProgressById({});
  }, [workspaceId]);

  const filtersKey = useMemo(
    () => (filters?.length ? JSON.stringify(filters) : ""),
    [filters],
  );
  const qKey = useMemo(() => q ?? "", [q]);
  const totalQueryKey = useMemo(
    () => [
      "documents-total",
      workspaceId,
      sort ?? "",
      qKey,
      lifecycle,
      filtersKey,
      joinOperator ?? "",
    ],
    [workspaceId, sort, qKey, lifecycle, filtersKey, joinOperator],
  );
  const queryKey = useMemo(
    () => [
      "documents",
      workspaceId,
      page,
      perPage,
      sort ?? "",
      qKey,
      lifecycle,
      filtersKey,
      joinOperator ?? "",
    ],
    [workspaceId, page, perPage, sort, qKey, lifecycle, filtersKey, joinOperator],
  );

  const documentsQuery = useQuery<DocumentPageResult>({
    queryKey,
    queryFn: async ({ signal }) => {
      const cachedTotal = queryClient.getQueryData<number>(totalQueryKey);
      const pageResult = await fetchWorkspaceDocuments(
        workspaceId,
        {
          limit: perPage,
          page,
          sort,
          q,
          lifecycle,
          filters,
          joinOperator: joinOperator ?? undefined,
          includeTotal: typeof cachedTotal !== "number",
        },
        signal,
      );

      if (typeof pageResult.meta.totalCount === "number") {
        queryClient.setQueryData(totalQueryKey, pageResult.meta.totalCount);
        return pageResult;
      }

      if (typeof cachedTotal === "number") {
        return {
          ...pageResult,
          meta: {
            ...pageResult.meta,
            totalCount: cachedTotal,
            totalIncluded: true,
          },
        };
      }

      return pageResult;
    },
    enabled: enabled && Boolean(workspaceId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });

  const items = documentsQuery.data?.items ?? [];
  const rows = useMemo(
    () =>
      items.map((item) =>
        ({
          ...item,
          uploadProgress: uploadProgressById[item.id] ?? null,
        }) satisfies DocumentRow,
      ),
    [items, uploadProgressById],
  );

  const documentsById = useMemo(() => {
    const next: Record<string, DocumentRow> = {};
    rows.forEach((row) => {
      next[row.id] = row;
    });
    return next;
  }, [rows]);

  const updateRow = useCallback(
    (documentId: string, updates: Partial<DocumentRow>) => {
      queryClient.setQueryData<DocumentPageResult | undefined>(queryKey, (prev) => {
        if (!prev?.items) return prev;
        const nextItems = prev.items.map((row) =>
          row.id === documentId ? { ...row, ...updates } : row,
        );
        return { ...prev, items: nextItems };
      });
    },
    [queryClient, queryKey],
  );

  const upsertRow = useCallback(
    (row: DocumentListRow) => {
      queryClient.setQueryData<DocumentPageResult | undefined>(queryKey, (prev) => {
        if (!prev?.items) return prev;
        const items = [...prev.items];
        const index = items.findIndex((item) => item.id === row.id);
        if (index >= 0) {
          items[index] = { ...items[index], ...row };
          return { ...prev, items };
        }
        if (page === 1) {
          items.unshift(row);
          return { ...prev, items: items.slice(0, perPage) };
        }
        return prev;
      });
    },
    [page, perPage, queryClient, queryKey],
  );

  const removeRow = useCallback(
    (documentId: string) => {
      queryClient.setQueryData<DocumentPageResult | undefined>(queryKey, (prev) => {
        if (!prev?.items) return prev;
        const nextItems = prev.items.filter((row) => row.id !== documentId);
        return { ...prev, items: nextItems };
      });
    },
    [queryClient, queryKey],
  );

  const setUploadProgress = useCallback(
    (documentId: string, percent: number | null) => {
      setUploadProgressById((prev) => {
        const next = { ...prev };
        if (percent === null) {
          delete next[documentId];
          return next;
        }
        next[documentId] = percent;
        return next;
      });
    },
    [],
  );

  const refreshSnapshot = useCallback(async () => {
    queryClient.removeQueries({ queryKey: totalQueryKey, exact: true });
    return documentsQuery.refetch();
  }, [documentsQuery, queryClient, totalQueryKey]);

  return {
    rows,
    documentsById,
    changesCursor: documentsQuery.data?.meta?.changesCursor ?? null,
    pageCount:
      typeof documentsQuery.data?.meta.totalCount === "number"
        ? Math.max(1, Math.ceil(documentsQuery.data.meta.totalCount / perPage))
        : 1,
    total:
      typeof documentsQuery.data?.meta.totalCount === "number"
        ? documentsQuery.data.meta.totalCount
        : null,
    isLoading: documentsQuery.isLoading,
    isFetching: documentsQuery.isFetching,
    error: documentsQuery.error instanceof Error ? documentsQuery.error.message : null,
    refreshSnapshot,
    updateRow,
    upsertRow,
    removeRow,
    setUploadProgress,
    queryKey,
    totalQueryKey,
  };
}
