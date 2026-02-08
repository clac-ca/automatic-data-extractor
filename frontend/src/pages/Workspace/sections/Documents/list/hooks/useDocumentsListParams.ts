import { useMemo } from "react";
import { useQueryState, useQueryStates } from "nuqs";

import type { DocumentLifecycle } from "@/api/documents";

import type { DocumentsListParams } from "../../shared/types";
import {
  buildDocumentsQuerySnapshot,
  createDocumentsSimpleFilterParsers,
  documentsFilterFlagParser,
  documentsFiltersParser,
  documentsJoinOperatorParser,
  documentsLifecycleParser,
  documentsPageParser,
  documentsPerPageParser,
  documentsSearchParser,
  documentsSortParser,
  resolveListFiltersForApi,
  type FilterMode,
} from "../state/queryState";

export function useDocumentsListParams({
  filterMode = "advanced",
  currentUserId = null,
}: {
  filterMode?: FilterMode;
  currentUserId?: string | null;
} = {}): DocumentsListParams {
  const [page] = useQueryState("page", documentsPageParser);
  const [perPage] = useQueryState("perPage", documentsPerPageParser);
  const [q] = useQueryState("q", documentsSearchParser);
  const [sorting] = useQueryState("sort", documentsSortParser);
  const [filtersState] = useQueryState("filters", documentsFiltersParser);
  const [joinOperator] = useQueryState("joinOperator", documentsJoinOperatorParser);
  const [filterFlag] = useQueryState("filterFlag", documentsFilterFlagParser);
  const [lifecycle] = useQueryState("lifecycle", documentsLifecycleParser);
  const simpleParsers = useMemo(createDocumentsSimpleFilterParsers, []);
  const [simpleFilterValues] = useQueryStates(simpleParsers);

  const snapshot = useMemo(
    () =>
      buildDocumentsQuerySnapshot({
        q,
        sort: sorting,
        filters: filtersState,
        joinOperator,
        filterFlag,
        lifecycle,
        simpleFilters: simpleFilterValues,
      }),
    [filterFlag, filtersState, joinOperator, lifecycle, q, simpleFilterValues, sorting],
  );

  const sort = useMemo(
    () => (snapshot.sort.length ? JSON.stringify(snapshot.sort) : null),
    [snapshot.sort],
  );

  const { filters, joinOperator: resolvedJoinOperator } = useMemo(
    () =>
      resolveListFiltersForApi({
        snapshot,
        filterMode,
        currentUserId,
      }),
    [currentUserId, filterMode, snapshot],
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
