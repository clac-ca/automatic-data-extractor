import { encodeFilters, type FilterItem, type FilterJoinOperator } from "@api/listing";
import { UNASSIGNED_KEY } from "@pages/Workspace/sections/Documents/filters";
import { getValidFilters } from "@/lib/data-table";
import { parseFiltersState } from "@/lib/parsers";

import type { DocumentsListParams, DocumentListRow } from "./types";

export const DEFAULT_PAGE_SIZE = 50;
export const DEFAULT_DOCUMENT_SORT = "-createdAt";

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
        return null;
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

type SortToken = { field: string; desc: boolean };

const SORT_FIELD_ACCESSORS: Record<string, (row: DocumentListRow) => string | number | null> = {
  id: (row) => row.id,
  workspaceId: (row) => row.workspaceId,
  name: (row) => row.name,
  status: (row) => row.status,
  fileType: (row) => row.fileType,
  byteSize: (row) => row.byteSize,
  createdAt: (row) => Date.parse(row.createdAt),
  updatedAt: (row) => Date.parse(row.updatedAt),
  activityAt: (row) => Date.parse(row.activityAt),
  latestRunAt: (row) =>
    Date.parse(row.latestRun?.completedAt ?? row.latestRun?.startedAt ?? ""),
};

function normalizeSortValue(value: string | number | null) {
  if (value == null || Number.isNaN(value)) return null;
  if (typeof value === "string") return value.toLowerCase();
  return value;
}

function compareValues(a: string | number | null, b: string | number | null) {
  const left = normalizeSortValue(a);
  const right = normalizeSortValue(b);
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  if (typeof left === "number" && typeof right === "number") {
    return left - right;
  }
  return String(left).localeCompare(String(right));
}

export function parseSortTokens(sort: string | null): SortToken[] {
  if (!sort) return [];
  return sort
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => {
      const desc = token.startsWith("-");
      const field = desc ? token.slice(1) : token;
      return { field, desc };
    });
}

export function buildDocumentsComparator(tokens: SortToken[]) {
  return (left: DocumentListRow, right: DocumentListRow) => {
    for (const token of tokens) {
      const accessor = SORT_FIELD_ACCESSORS[token.field];
      if (!accessor) {
        continue;
      }
      const diff = compareValues(accessor(left), accessor(right));
      if (diff !== 0) {
        return token.desc ? -diff : diff;
      }
    }
    return String(left.id).localeCompare(String(right.id));
  };
}

export function supportsSortTokens(tokens: SortToken[]) {
  return tokens.every((token) => Boolean(SORT_FIELD_ACCESSORS[token.field]));
}

export function evaluateDocumentFilters(
  row: DocumentListRow,
  filters: FilterItem[],
  joinOperator: FilterJoinOperator | null,
  q: string | null,
) {
  let requiresRefresh = false;
  const results: boolean[] = [];

  if (q) {
    return { matches: false, requiresRefresh: true };
  }

  for (const filter of filters) {
    const { id, operator, value } = filter;
    const values = Array.isArray(value) ? value : value != null ? [value] : [];

    if (id === "status") {
      const statuses = values.map(String);
      const match = statuses.includes(String(row.status));
      results.push(operator === "ne" || operator === "notIn" ? !match : match);
      continue;
    }

    if (id === "runStatus") {
      const status = row.latestRun?.status ?? null;
      const match = status != null && values.map(String).includes(String(status));
      results.push(operator === "ne" || operator === "notIn" ? !match : match);
      continue;
    }

    if (id === "fileType") {
      const match = values.map(String).includes(String(row.fileType));
      results.push(operator === "notIn" ? !match : match);
      continue;
    }

    if (id === "tags") {
      const tags = new Set(row.tags ?? []);
      if (operator === "isEmpty") {
        results.push(tags.size === 0);
        continue;
      }
      if (operator === "isNotEmpty") {
        results.push(tags.size > 0);
        continue;
      }
      const tagValues = new Set(values.map(String));
      const anyMatch = Array.from(tagValues).some((tag) => tags.has(tag));
      const match = operator === "eq" ? tagValues.has(values[0] ? String(values[0]) : "") : anyMatch;
      results.push(operator === "notIn" ? !match : match);
      continue;
    }

    if (id === "assigneeId") {
      const assigneeId = row.assignee?.id ?? null;
      if (operator === "isEmpty") {
        results.push(assigneeId == null);
        continue;
      }
      if (operator === "isNotEmpty") {
        results.push(assigneeId != null);
        continue;
      }
      const match = assigneeId != null && values.map(String).includes(String(assigneeId));
      results.push(operator === "notIn" ? !match : match);
      continue;
    }

    if (id === "uploaderId") {
      const uploaderId = row.uploader?.id ?? null;
      if (operator === "isEmpty") {
        results.push(uploaderId == null);
        continue;
      }
      if (operator === "isNotEmpty") {
        results.push(uploaderId != null);
        continue;
      }
      const match = uploaderId != null && values.map(String).includes(String(uploaderId));
      results.push(operator === "notIn" ? !match : match);
      continue;
    }

    if (id === "createdAt" || id === "updatedAt" || id === "activityAt") {
      const source = Date.parse(row[id]);
      const compareValue = Array.isArray(value) ? value : value != null ? [value] : [];
      if (operator === "between" && compareValue.length >= 2) {
        const [start, end] = compareValue;
        const startTs = Date.parse(String(start));
        const endTs = Date.parse(String(end));
        results.push(source >= startTs && source <= endTs);
        continue;
      }
      const numeric = Number(compareValue[0]);
      const target = Number.isNaN(numeric) ? Date.parse(String(compareValue[0])) : numeric;
      if (operator === "lt") {
        results.push(source < target);
        continue;
      }
      if (operator === "lte") {
        results.push(source <= target);
        continue;
      }
      if (operator === "gt") {
        results.push(source > target);
        continue;
      }
      if (operator === "gte") {
        results.push(source >= target);
        continue;
      }
    }

    if (id === "byteSize") {
      const numericValues = values.map((entry) => Number(entry)).filter((entry) => !Number.isNaN(entry));
      if (operator === "between" && numericValues.length >= 2) {
        results.push(row.byteSize >= numericValues[0] && row.byteSize <= numericValues[1]);
        continue;
      }
      if (operator === "lt") {
        results.push(row.byteSize < numericValues[0]);
        continue;
      }
      if (operator === "lte") {
        results.push(row.byteSize <= numericValues[0]);
        continue;
      }
      if (operator === "gt") {
        results.push(row.byteSize > numericValues[0]);
        continue;
      }
      if (operator === "gte") {
        results.push(row.byteSize >= numericValues[0]);
        continue;
      }
      if (operator === "eq") {
        results.push(row.byteSize === numericValues[0]);
        continue;
      }
      if (operator === "notIn") {
        results.push(!numericValues.includes(row.byteSize));
        continue;
      }
      if (operator === "in") {
        results.push(numericValues.includes(row.byteSize));
        continue;
      }
    }

    if (id === "hasOutput") {
      const match = Boolean(row.latestSuccessfulRun) === Boolean(value);
      results.push(operator === "ne" ? !match : match);
      continue;
    }

    requiresRefresh = true;
    results.push(false);
  }

  const join = joinOperator ?? "and";
  let matched = results.length === 0 ? true : join === "or" ? results.some(Boolean) : results.every(Boolean);

  if (q) {
    const tokens = q
      .split(/\s+/)
      .map((token) => token.trim().toLowerCase())
      .filter(Boolean);
    if (tokens.length > 0) {
      const searchable = [
        row.name,
        row.status,
        row.uploader?.name,
        row.uploader?.email,
        ...(row.tags ?? []),
      ]
        .filter(Boolean)
        .map((value) => String(value).toLowerCase());
      const tokenMatch = tokens.every((token) =>
        searchable.some((value) => value.includes(token)),
      );
      matched = matched && tokenMatch;
    }
  }

  return { matches: matched, requiresRefresh };
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
