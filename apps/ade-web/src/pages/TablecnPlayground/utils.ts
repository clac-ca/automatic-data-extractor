import { getValidFilters } from "@components/tablecn/lib/data-table";
import { parseFiltersState } from "@components/tablecn/lib/parsers";

import type { DocumentsListParams } from "./types";

export const DEFAULT_PAGE_SIZE = 50;

export function parseNumberParam(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

export function formatTimestamp(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

type SortStateItem = { id: string; desc?: boolean };

const FILTER_OPERATOR_MAP: Record<string, string> = {
  inArray: "in",
  notInArray: "notIn",
  isBetween: "between",
};

function normalizeSortParam(value: string | null) {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        const items = parsed
          .map((item) => item as SortStateItem)
          .filter((item) => item && typeof item.id === "string");
        if (items.length > 0) {
          return items
            .map((item) => `${item.desc ? "-" : ""}${item.id}`)
            .join(",");
        }
      }
    } catch {
      return trimmed;
    }
  }

  return trimmed;
}

function normalizeFiltersParam(value: string | null) {
  if (!value) return null;

  const parsed = parseFiltersState(value);
  if (parsed.length === 0) return null;

  const normalized = getValidFilters(parsed).map((filter) => {
    const mappedOperator =
      FILTER_OPERATOR_MAP[filter.operator] ?? filter.operator;
    const next: Record<string, unknown> = {
      ...filter,
      operator: mappedOperator,
    };
    return next;
  });

  if (normalized.length === 0) return null;

  return JSON.stringify(normalized);
}

export function buildDocumentsListQuery(params: DocumentsListParams) {
  const query = new URLSearchParams();
  query.set("page", String(params.page));
  query.set("perPage", String(params.perPage));

  const sort = normalizeSortParam(params.sort);
  if (sort) {
    query.set("sort", sort);
  }

  const filters = normalizeFiltersParam(params.filters);
  if (filters) {
    query.set("filters", filters);
  }

  if (params.joinOperator) {
    query.set("joinOperator", params.joinOperator);
  }

  if (params.q) {
    query.set("q", params.q);
  }

  return query;
}
