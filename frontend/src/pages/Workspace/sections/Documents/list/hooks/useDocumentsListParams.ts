import { useMemo } from "react";
import { useQueryState } from "nuqs";

import type { DocumentLifecycle } from "@/api/documents";

import type { DocumentsListParams } from "../../shared/types";
import {
  buildDocumentsQuerySnapshot,
  documentsFiltersParser,
  documentsJoinOperatorParser,
  documentsLifecycleParser,
  documentsPageParser,
  documentsPerPageParser,
  documentsSearchParser,
  documentsSortParser,
  resolveListFiltersForApi,
} from "../state/queryState";

export function useDocumentsListParams({
  currentUserId = null,
}: {
  currentUserId?: string | null;
} = {}): DocumentsListParams {
  const [page] = useQueryState("page", documentsPageParser);
  const [perPage] = useQueryState("perPage", documentsPerPageParser);
  const [q] = useQueryState("q", documentsSearchParser);
  const [sorting] = useQueryState("sort", documentsSortParser);
  const [filtersState] = useQueryState("filters", documentsFiltersParser);
  const [joinOperator] = useQueryState("joinOperator", documentsJoinOperatorParser);
  const [lifecycle] = useQueryState("lifecycle", documentsLifecycleParser);

  const snapshot = useMemo(
    () =>
      buildDocumentsQuerySnapshot({
        q,
        sort: sorting,
        filters: filtersState,
        joinOperator,
        lifecycle,
      }),
    [filtersState, joinOperator, lifecycle, q, sorting],
  );

  const sort = useMemo(
    () => (snapshot.sort.length ? JSON.stringify(snapshot.sort) : null),
    [snapshot.sort],
  );

  const { filters, joinOperator: resolvedJoinOperator } = useMemo(
    () =>
      resolveListFiltersForApi({
        snapshot,
        currentUserId,
      }),
    [currentUserId, snapshot],
  );

  return {
    page,
    perPage,
    sort,
    q: snapshot.q,
    filters,
    joinOperator: resolvedJoinOperator,
    lifecycle: snapshot.lifecycle as DocumentLifecycle,
  };
}
