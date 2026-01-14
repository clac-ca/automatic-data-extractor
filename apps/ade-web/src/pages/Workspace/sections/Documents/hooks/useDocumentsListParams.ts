import { useMemo } from "react";
import {
  parseAsArrayOf,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
  type SingleParser,
  useQueryState,
  useQueryStates,
} from "nuqs";

import { getFiltersStateParser, getSortingStateParser } from "@/lib/parsers";
import { getDefaultFilterOperator, getValidFilters } from "@/lib/data-table";
import type { FilterItem, FilterJoinOperator } from "@api/listing";

import {
  DEFAULT_PAGE_SIZE,
  DEFAULT_SORTING,
  DOCUMENTS_FILTER_IDS,
  DOCUMENTS_SIMPLE_FILTERS,
  DOCUMENTS_SORT_IDS,
} from "../constants";
import type { DocumentListRow, DocumentsListParams } from "../types";

function toApiFilters(filters: ReturnType<typeof getValidFilters<DocumentListRow>>): FilterItem[] {
  return filters.map(({ id, operator, value }) => ({ id, operator, value }));
}

type FilterMode = "advanced" | "simple";

function createSimpleFilterParsers() {
  const parsers: Record<string, SingleParser<string> | SingleParser<string[]>> = {};

  Object.entries(DOCUMENTS_SIMPLE_FILTERS).forEach(([id, variant]) => {
    if (variant === "multiSelect" || variant === "select") {
      parsers[id] = parseAsArrayOf(parseAsString, ",");
    } else {
      parsers[id] = parseAsString;
    }
  });

  return parsers;
}

export function useDocumentsListParams({
  filterMode = "advanced",
}: {
  filterMode?: FilterMode;
} = {}): DocumentsListParams {
  const [page] = useQueryState("page", parseAsInteger.withDefault(1));
  const [perPage] = useQueryState(
    "perPage",
    parseAsInteger.withDefault(DEFAULT_PAGE_SIZE),
  );
  const [sorting] = useQueryState(
    "sort",
    getSortingStateParser<DocumentListRow>(DOCUMENTS_SORT_IDS).withDefault(
      DEFAULT_SORTING,
    ),
  );
  const sort = useMemo(
    () => (sorting?.length ? JSON.stringify(sorting) : null),
    [sorting],
  );
  const [filtersValue] = useQueryState(
    "filters",
    getFiltersStateParser<DocumentListRow>(DOCUMENTS_FILTER_IDS),
  );
  const advancedFilters = useMemo(() => {
    if (!filtersValue) return null;
    const parsed = getValidFilters(filtersValue);
    if (!parsed.length) return null;
    return toApiFilters(parsed);
  }, [filtersValue]);
  const [joinOperator] = useQueryState(
    "joinOperator",
    parseAsStringEnum(["and", "or"]).withDefault("and"),
  );

  const simpleFilterParsers = useMemo(createSimpleFilterParsers, []);
  const [simpleFilterValues] = useQueryStates(simpleFilterParsers);
  const simpleFilters = useMemo(() => {
    const items: FilterItem[] = [];

    Object.entries(DOCUMENTS_SIMPLE_FILTERS).forEach(([id, variant]) => {
      const rawValue = simpleFilterValues[id];
      if (rawValue === null || rawValue === undefined) return;

      if (Array.isArray(rawValue)) {
        const values = rawValue.filter(Boolean);
        if (!values.length) return;
        items.push({
          id,
          operator: getDefaultFilterOperator(variant),
          value: values,
        });
        return;
      }

      if (rawValue === "") return;
      items.push({
        id,
        operator: getDefaultFilterOperator(variant),
        value: rawValue,
      });
    });

    return items.length ? items : null;
  }, [simpleFilterValues]);

  const filters = filterMode === "advanced" ? advancedFilters : simpleFilters;
  const resolvedJoinOperator =
    filterMode === "advanced"
      ? (joinOperator as FilterJoinOperator | null)
      : filters?.length
        ? "and"
        : null;

  return {
    page,
    perPage,
    sort,
    filters,
    joinOperator: resolvedJoinOperator,
  };
}
