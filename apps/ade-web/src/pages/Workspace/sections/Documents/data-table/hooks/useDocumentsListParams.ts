import { parseAsInteger, parseAsStringEnum, useQueryState } from "nuqs";
import { useMemo } from "react";

import { getFiltersStateParser, getSortingStateParser } from "@/lib/parsers";
import { getValidFilters } from "@/lib/data-table";

import { DEFAULT_PAGE_SIZE } from "../utils";
import type { DocumentsListParams } from "../types";
import type { DocumentListRow } from "../types";

const SORTABLE_COLUMNS = new Set([
  "id",
  "name",
  "status",
  "createdAt",
  "updatedAt",
  "activityAt",
  "latestRunAt",
  "byteSize",
  "source",
]);

const FILTERABLE_COLUMNS = new Set([
  "status",
  "name",
  "runStatus",
  "fileType",
  "tags",
  "assigneeId",
  "uploaderId",
  "createdAt",
  "updatedAt",
  "activityAt",
  "byteSize",
  "hasOutput",
  "source",
]);

export function useDocumentsListParams(): DocumentsListParams {
  const [page] = useQueryState(
    "page",
    parseAsInteger.withDefault(1),
  );
  const [perPage] = useQueryState(
    "perPage",
    parseAsInteger.withDefault(DEFAULT_PAGE_SIZE),
  );
  const [sorting] = useQueryState(
    "sort",
    getSortingStateParser<DocumentListRow>(SORTABLE_COLUMNS),
  );
  const sort = useMemo(
    () => (sorting?.length ? JSON.stringify(sorting) : null),
    [sorting],
  );
  const [filtersValue] = useQueryState(
    "filters",
    getFiltersStateParser<DocumentListRow>(FILTERABLE_COLUMNS),
  );
  const filters = useMemo(() => {
    if (!filtersValue) return null;
    const parsed = getValidFilters(filtersValue);
    return parsed.length ? parsed : null;
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
    joinOperator,
  };
}
