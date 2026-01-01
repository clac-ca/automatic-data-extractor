import { encodeFilters, type FilterItem } from "@api/listing";
import { UNASSIGNED_KEY } from "@pages/Workspace/sections/Documents/filters";
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

const RELATIVE_RANGE_PATTERN = /^(-?\d+)\s*(days|weeks|months)$/i;

function startOfDay(date: Date) {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

function endOfDay(date: Date) {
  const next = new Date(date);
  next.setHours(23, 59, 59, 999);
  return next;
}

function addDays(date: Date, amount: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function toIsoString(value: number): string {
  return new Date(value).toISOString();
}

function rangeForTimestamp(value: number): [string, string] | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const start = startOfDay(date);
  const end = endOfDay(date);
  return [toIsoString(start.getTime()), toIsoString(end.getTime())];
}

function resolveRelativeDateRange(value: unknown): [string, string] | null {
  if (Array.isArray(value)) {
    return resolveRelativeDateRange(value[0]);
  }

  if (typeof value === "number") {
    return rangeForTimestamp(value);
  }

  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;

  const match = trimmed.match(RELATIVE_RANGE_PATTERN);
  if (match) {
    const amount = Number.parseInt(match[1] ?? "", 10);
    const unit = match[2];
    if (Number.isNaN(amount) || !unit) return null;

    const today = new Date();
    let startDate: Date;
    let endDate: Date;

    switch (unit) {
      case "days":
        startDate = startOfDay(addDays(today, amount));
        endDate = endOfDay(startDate);
        break;
      case "weeks":
        startDate = startOfDay(addDays(today, amount * 7));
        endDate = endOfDay(addDays(startDate, 6));
        break;
      case "months":
        startDate = startOfDay(addDays(today, amount * 30));
        endDate = endOfDay(addDays(startDate, 29));
        break;
      default:
        return null;
    }

    return [toIsoString(startDate.getTime()), toIsoString(endDate.getTime())];
  }

  const timestamp = Number(trimmed);
  if (!Number.isNaN(timestamp)) {
    return rangeForTimestamp(timestamp);
  }

  return null;
}

function normalizeDateValue(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === "number") return toIsoString(value);
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const numeric = Number(trimmed);
    if (!Number.isNaN(numeric)) return toIsoString(numeric);
    const parsed = Date.parse(trimmed);
    if (!Number.isNaN(parsed)) return toIsoString(parsed);
  }
  return null;
}

function normalizeNumberValue(value: unknown) {
  if (value == null) return null;
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const numeric = Number(trimmed);
    return Number.isNaN(numeric) ? value : numeric;
  }
  return value;
}

function normalizeBooleanValue(value: unknown) {
  if (value == null) return null;
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (!normalized) return null;
    if (normalized === "true") return true;
    if (normalized === "false") return false;
  }
  return value;
}

function normalizeFilterValue(filter: { id: string; variant: string; value: unknown }) {
  if (filter.variant === "date" || filter.variant === "dateRange") {
    if (Array.isArray(filter.value)) {
      return filter.value.map((entry) => normalizeDateValue(entry)).filter(Boolean);
    }
    return normalizeDateValue(filter.value);
  }

  if (filter.variant === "number" || filter.variant === "range") {
    if (Array.isArray(filter.value)) {
      return filter.value.map((entry) => normalizeNumberValue(entry)).filter((value) => value !== null);
    }
    return normalizeNumberValue(filter.value);
  }

  if (filter.variant === "boolean") {
    if (Array.isArray(filter.value)) {
      return filter.value.map((entry) => normalizeBooleanValue(entry)).filter((value) => value !== null);
    }
    return normalizeBooleanValue(filter.value);
  }

  if (filter.id === "assigneeId") {
    const values = Array.isArray(filter.value) ? filter.value : [filter.value];
    const includeUnassigned = values.includes(UNASSIGNED_KEY);
    const cleaned = values.filter((item) => item != null && item !== UNASSIGNED_KEY);
    return includeUnassigned ? [...cleaned, null] : cleaned;
  }

  if (filter.id === "hasOutput") {
    if (Array.isArray(filter.value)) {
      return filter.value.map((item) => String(item).toLowerCase() === "true");
    }
    if (typeof filter.value === "string") {
      return filter.value.toLowerCase() === "true";
    }
  }

  return filter.value;
}

export function normalizeDocumentsSort(value: string | null) {
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

export function normalizeDocumentsFilters(value: string | null): FilterItem[] {
  if (!value) return [];

  const parsed = parseFiltersState(value);
  if (parsed.length === 0) return [];

  const normalized = getValidFilters(parsed)
    .map((filter) => {
      if (filter.operator === "isRelativeToToday") {
        const range = resolveRelativeDateRange(filter.value);
        if (!range) return null;
        return {
          id: filter.id,
          operator: "between",
          value: range,
        } satisfies FilterItem;
      }

      const mappedOperator =
        FILTER_OPERATOR_MAP[filter.operator] ?? filter.operator;
      const normalizedValue = normalizeFilterValue(filter);
      const base: FilterItem = {
        id: filter.id,
        operator: mappedOperator as FilterItem["operator"],
      };
      if (mappedOperator !== "isEmpty" && mappedOperator !== "isNotEmpty") {
        base.value = normalizedValue;
      }
      return {
        ...base,
      } satisfies FilterItem;
    })
    .filter((value): value is FilterItem => Boolean(value));

  return normalized;
}

export function buildDocumentsListQuery(params: DocumentsListParams) {
  const query = new URLSearchParams();
  query.set("perPage", String(params.perPage));

  const sort = normalizeDocumentsSort(params.sort);
  if (sort) {
    query.set("sort", sort);
  }

  const filters = normalizeDocumentsFilters(params.filters);
  const encodedFilters = encodeFilters(filters);
  if (encodedFilters) {
    query.set("filters", encodedFilters);
  }

  if (params.joinOperator) {
    query.set("joinOperator", params.joinOperator);
  }

  if (params.q) {
    query.set("q", params.q);
  }

  return query;
}
