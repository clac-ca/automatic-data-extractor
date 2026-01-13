import { useMemo } from "react";
import { parseAsInteger, parseAsStringEnum, useQueryState } from "nuqs";

import { getFiltersStateParser, getSortingStateParser } from "@/lib/parsers";
import { getValidFilters } from "@/lib/data-table";
import type { FilterItem, FilterJoinOperator } from "@api/listing";

import { DEFAULT_PAGE_SIZE, RUNS_FILTER_IDS, RUNS_SORT_IDS } from "../constants";
import type { RunListRow, RunsListParams } from "../types";

function toApiFilters(filters: ReturnType<typeof getValidFilters<RunListRow>>): FilterItem[] {
  return filters.map(({ id, operator, value }) => ({ id, operator, value }));
}

export function useRunsListParams(): RunsListParams {
  const [page] = useQueryState("page", parseAsInteger.withDefault(1));
  const [perPage] = useQueryState(
    "perPage",
    parseAsInteger.withDefault(DEFAULT_PAGE_SIZE),
  );
  const [sorting] = useQueryState(
    "sort",
    getSortingStateParser<RunListRow>(RUNS_SORT_IDS),
  );
  const sort = useMemo(
    () => (sorting?.length ? JSON.stringify(sorting) : null),
    [sorting],
  );
  const [filtersValue] = useQueryState(
    "filters",
    getFiltersStateParser<RunListRow>(RUNS_FILTER_IDS),
  );
  const filters = useMemo(() => {
    if (!filtersValue) return null;
    const parsed = getValidFilters(filtersValue);
    if (!parsed.length) return null;
    return toApiFilters(parsed);
  }, [filtersValue]);
  const [joinOperator] = useQueryState(
    "joinOperator",
    parseAsStringEnum(["and", "or"]),
  );

  return {
    page,
    perPage,
    sort,
    filters,
    joinOperator: joinOperator as FilterJoinOperator | null,
  };
}
