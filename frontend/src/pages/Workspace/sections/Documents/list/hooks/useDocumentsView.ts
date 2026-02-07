import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaceDocuments, type DocumentListRow, type DocumentPageResult } from "@/api/documents";
import type { FilterItem, FilterJoinOperator } from "@/api/listing";
import { useCursorPager } from "@/hooks/use-cursor-pager";

import type { DocumentRow } from "../../shared/types";

export function useDocumentsView({
  workspaceId,
  page,
  perPage,
  sort,
  q,
  filters,
  joinOperator,
  enabled = true,
}: {
  workspaceId: string;
  page: number;
  perPage: number;
  sort: string | null;
  q: string | null;
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
  const cursorKey = useMemo(
    () => [workspaceId, perPage, sort ?? "", qKey, filtersKey, joinOperator ?? ""].join("|"),
    [workspaceId, perPage, sort, qKey, filtersKey, joinOperator],
  );
  const queryKey = useMemo(
    () => ["documents", workspaceId, page, perPage, sort ?? "", qKey, filtersKey, joinOperator ?? ""],
    [workspaceId, page, perPage, sort, qKey, filtersKey, joinOperator],
  );

  const cursorPager = useCursorPager<DocumentPageResult>({
    page,
    limit: perPage,
    includeTotal: true,
    resetKey: cursorKey,
    fetchPage: ({ cursor, limit, includeTotal, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          limit,
          cursor,
          sort,
          q,
          filters,
          joinOperator: joinOperator ?? undefined,
          includeTotal,
        },
        signal,
      ),
  });

  const documentsQuery = useQuery<DocumentPageResult>({
    queryKey,
    queryFn: ({ signal }) => cursorPager.fetchCurrentPage(signal),
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
    refreshSnapshot: documentsQuery.refetch,
    updateRow,
    upsertRow,
    removeRow,
    setUploadProgress,
    queryKey,
  };
}
