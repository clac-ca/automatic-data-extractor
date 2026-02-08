import {
  parseAsArrayOf,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
  type SingleParser,
} from "nuqs";

import { getDefaultFilterOperator, getValidFilters } from "@/lib/data-table";
import { getFiltersStateParser, getSortingStateParser } from "@/lib/parsers";
import type { FilterItem, FilterJoinOperator } from "@/api/listing";
import type { ExtendedColumnFilter, ExtendedColumnSort, FilterVariant } from "@/types/data-table";
import type { components } from "@/types";

import {
  DEFAULT_PAGE_SIZE,
  DOCUMENTS_FILTER_IDS,
  DOCUMENTS_SIMPLE_FILTERS,
  DOCUMENTS_SORT_IDS,
} from "../../shared/constants";
import type { DocumentListRow } from "../../shared/types";

type SortState = ExtendedColumnSort<DocumentListRow>[];
type FiltersState = ExtendedColumnFilter<DocumentListRow>[];
type FilterValue = ExtendedColumnFilter<DocumentListRow>["value"];
type JoinOperator = "and" | "or";
type Lifecycle = "active" | "deleted";
type FilterFlag = "advancedFilters" | null;
type SimpleFilters = Record<string, string | string[]>;
export type FilterMode = "advanced" | "simple";
type DocumentViewQueryState = components["schemas"]["DocumentViewQueryState"];

type QuerySnapshotInput = {
  q: string | null;
  sort: unknown;
  filters: unknown;
  joinOperator: unknown;
  filterFlag: unknown;
  lifecycle: unknown;
  simpleFilters: Record<string, string | string[] | null | undefined>;
};

export type DocumentsQuerySnapshot = {
  q: string | null;
  sort: SortState;
  filters: FiltersState;
  joinOperator: JoinOperator;
  filterFlag: FilterFlag;
  lifecycle: Lifecycle;
  simpleFilters: SimpleFilters;
};

const ARRAY_SEPARATOR = ",";

export const documentsPageParser = parseAsInteger.withDefault(1);
export const documentsPerPageParser = parseAsInteger.withDefault(DEFAULT_PAGE_SIZE);
export const documentsViewIdParser = parseAsString;
export const documentsSortParser = getSortingStateParser<DocumentListRow>(DOCUMENTS_SORT_IDS);
export const documentsFiltersParser = getFiltersStateParser<DocumentListRow>(DOCUMENTS_FILTER_IDS);
export const documentsJoinOperatorParser = parseAsStringEnum(["and", "or"]).withDefault("and");
export const documentsFilterFlagParser = parseAsStringEnum(["advancedFilters"]).withOptions({
  clearOnDefault: true,
});
export const documentsLifecycleParser = parseAsStringEnum(["active", "deleted"]).withDefault("active");
export const documentsSearchParser = parseAsString;

function normalizeString(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed ? trimmed : null;
}

export function normalizeSortingState(value: unknown): SortState {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is ExtendedColumnSort<DocumentListRow> =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as { id?: unknown }).id === "string" &&
      typeof (item as { desc?: unknown }).desc === "boolean",
  );
}

export function normalizeFiltersState(value: unknown): FiltersState {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is ExtendedColumnFilter<DocumentListRow> =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as { id?: unknown }).id === "string" &&
      "operator" in (item as object),
  );
}

export function normalizeSimpleFilters(
  source: Record<string, string | string[] | null | undefined>,
): SimpleFilters {
  const output: SimpleFilters = {};
  Object.entries(source).forEach(([key, raw]) => {
    if (raw === null || raw === undefined) return;
    if (Array.isArray(raw)) {
      const filtered = raw.filter(Boolean);
      if (filtered.length > 0) output[key] = filtered;
      return;
    }
    const trimmed = raw.trim();
    if (trimmed) output[key] = trimmed;
  });
  return output;
}

function normalizeJoinOperator(value: unknown): JoinOperator {
  return value === "or" ? "or" : "and";
}

function normalizeFilterFlag(value: unknown): FilterFlag {
  return value === "advancedFilters" ? "advancedFilters" : null;
}

function normalizeLifecycle(value: unknown): Lifecycle {
  return value === "deleted" ? "deleted" : "active";
}

export function buildDocumentsQuerySnapshot(input: QuerySnapshotInput): DocumentsQuerySnapshot {
  return {
    q: normalizeString(input.q),
    sort: normalizeSortingState(input.sort),
    filters: normalizeFiltersState(input.filters),
    joinOperator: normalizeJoinOperator(input.joinOperator),
    filterFlag: normalizeFilterFlag(input.filterFlag),
    lifecycle: normalizeLifecycle(input.lifecycle),
    simpleFilters: normalizeSimpleFilters(input.simpleFilters),
  };
}

export function createDocumentsSimpleFilterParsers() {
  const parsers: Record<string, SingleParser<string> | SingleParser<string[]>> = {};
  Object.entries(DOCUMENTS_SIMPLE_FILTERS).forEach(([id, variant]) => {
    if (
      variant === "multiSelect" ||
      variant === "select" ||
      variant === "dateRange" ||
      variant === "range"
    ) {
      parsers[id] = parseAsArrayOf(parseAsString, ARRAY_SEPARATOR);
    } else {
      parsers[id] = parseAsString;
    }
  });
  return parsers;
}

function resolveAssigneeTokenValue(value: string, currentUserId: string | null): string {
  return value === "me" && currentUserId ? currentUserId : value;
}

function resolveAssigneeToken(value: FilterValue, currentUserId: string | null): FilterValue {
  if (value === "me" && currentUserId) return currentUserId;
  if (Array.isArray(value)) {
    return value.map((item) => resolveAssigneeTokenValue(item, currentUserId));
  }
  return value;
}

export function encodeAssigneeToken(value: FilterValue, currentUserId: string): FilterValue {
  if (value === currentUserId) return "me";
  if (Array.isArray(value)) {
    return value.map((item) => (item === currentUserId ? "me" : item));
  }
  return value;
}

function toApiFilters(filters: ReturnType<typeof getValidFilters<DocumentListRow>>): FilterItem[] {
  return filters.map(({ id, operator, value }) => ({ id, operator, value }));
}

function normalizeSimpleFilterToApiItems({
  snapshot,
  currentUserId,
}: {
  snapshot: DocumentsQuerySnapshot;
  currentUserId: string | null;
}): FilterItem[] | null {
  const items: FilterItem[] = [];

  Object.entries(DOCUMENTS_SIMPLE_FILTERS).forEach(([id, variant]) => {
    const rawValue = snapshot.simpleFilters[id];
    if (rawValue === null || rawValue === undefined) return;

    if (Array.isArray(rawValue)) {
      const values = rawValue.filter(Boolean);
      if (!values.length) return;
      if ((variant === "dateRange" || variant === "range") && values.length < 2) return;
      if (id === "lastRunPhase" && values.includes("__empty__")) {
        items.push({ id, operator: "isEmpty" });
        return;
      }
      if (id === "assigneeId") {
        if (values.includes("__empty__")) {
          items.push({ id, operator: "isEmpty" });
          return;
        }
        items.push({
          id,
          operator: getDefaultFilterOperator(variant),
          value: values.map((value) => resolveAssigneeTokenValue(value, currentUserId)),
        });
        return;
      }
      items.push({
        id,
        operator: variant === "dateRange" || variant === "range" ? "isBetween" : getDefaultFilterOperator(variant),
        value: values,
      });
      return;
    }

    if (rawValue === "") return;
    if (id === "assigneeId") {
      if (rawValue === "__empty__") {
        items.push({ id, operator: "isEmpty" });
        return;
      }
      items.push({
        id,
        operator: getDefaultFilterOperator(variant),
        value: resolveAssigneeTokenValue(rawValue, currentUserId),
      });
      return;
    }
    items.push({
      id,
      operator: getDefaultFilterOperator(variant),
      value: rawValue,
    });
  });

  return items.length ? items : null;
}

function normalizeAdvancedFiltersToApiItems({
  snapshot,
  currentUserId,
}: {
  snapshot: DocumentsQuerySnapshot;
  currentUserId: string | null;
}): FilterItem[] | null {
  if (!snapshot.filters.length) return null;
  const parsed = getValidFilters(snapshot.filters).map((filter) => {
    if (filter.id !== "assigneeId") return filter;
    const next = Array.isArray(filter.value)
      ? filter.value.map((value) => resolveAssigneeTokenValue(value, currentUserId))
      : resolveAssigneeToken(filter.value, currentUserId);
    return { ...filter, value: next };
  });
  return parsed.length ? toApiFilters(parsed) : null;
}

export function resolveListFiltersForApi({
  snapshot,
  filterMode,
  currentUserId,
}: {
  snapshot: DocumentsQuerySnapshot;
  filterMode: FilterMode;
  currentUserId: string | null;
}): { filters: FilterItem[] | null; joinOperator: FilterJoinOperator | null } {
  if (filterMode === "advanced") {
    const filters = normalizeAdvancedFiltersToApiItems({ snapshot, currentUserId });
    return {
      filters,
      joinOperator: snapshot.joinOperator as FilterJoinOperator,
    };
  }

  const filters = normalizeSimpleFilterToApiItems({ snapshot, currentUserId });
  return {
    filters,
    joinOperator: filters?.length ? "and" : null,
  };
}

export function hasExplicitListState(snapshot: DocumentsQuerySnapshot): boolean {
  const hasSimple = Object.keys(snapshot.simpleFilters).length > 0;
  return Boolean(
    snapshot.q ||
      snapshot.sort.length > 0 ||
      snapshot.filters.length > 0 ||
      snapshot.joinOperator === "or" ||
      snapshot.filterFlag === "advancedFilters" ||
      snapshot.lifecycle === "deleted" ||
      hasSimple,
  );
}

export function canonicalizeSnapshotForViewPersistence(
  snapshot: DocumentsQuerySnapshot,
): DocumentsQuerySnapshot {
  if (snapshot.filterFlag === "advancedFilters") {
    return {
      ...snapshot,
      simpleFilters: {},
    };
  }
  return {
    ...snapshot,
    filters: [],
    joinOperator: "and",
    filterFlag: null,
  };
}

export function parseViewQueryStateToSnapshot(
  queryState: Record<string, unknown> | null | undefined,
): DocumentsQuerySnapshot {
  const value = queryState ?? {};
  const rawSimpleFilters =
    value.simpleFilters && typeof value.simpleFilters === "object"
      ? (value.simpleFilters as Record<string, string | string[] | null | undefined>)
      : {};

  return buildDocumentsQuerySnapshot({
    q: typeof value.q === "string" ? value.q : null,
    sort: value.sort,
    filters: value.filters,
    joinOperator: value.joinOperator,
    filterFlag: value.filterFlag,
    lifecycle: value.lifecycle,
    simpleFilters: rawSimpleFilters,
  });
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => canonicalize(item));
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => [key, canonicalize(item)]);
    return Object.fromEntries(entries);
  }
  return value;
}

export function areSnapshotsEqual(a: DocumentsQuerySnapshot, b: DocumentsQuerySnapshot): boolean {
  return JSON.stringify(canonicalize(a)) === JSON.stringify(canonicalize(b));
}

function encodeSimpleFiltersForView(simpleFilters: SimpleFilters, currentUserId: string): SimpleFilters {
  const next: SimpleFilters = {};
  Object.entries(simpleFilters).forEach(([key, value]) => {
    if (key !== "assigneeId") {
      next[key] = value;
      return;
    }
    const encoded = encodeAssigneeToken(value, currentUserId);
    if (typeof encoded === "string" || Array.isArray(encoded)) {
      next[key] = encoded;
    }
  });
  return next;
}

export function encodeSnapshotForViewPersistence({
  snapshot,
  currentUserId,
}: {
  snapshot: DocumentsQuerySnapshot;
  currentUserId: string;
}): DocumentViewQueryState {
  const canonical = canonicalizeSnapshotForViewPersistence(snapshot);
  const filters: FiltersState = canonical.filters.map((item) => {
    if (item.id !== "assigneeId") return item;
    return {
      ...item,
      value: encodeAssigneeToken(item.value, currentUserId),
    };
  });

  return {
    lifecycle: canonical.lifecycle,
    q: canonical.q,
    sort: canonical.sort as unknown as DocumentViewQueryState["sort"],
    filters: filters as unknown as DocumentViewQueryState["filters"],
    joinOperator: canonical.joinOperator,
    filterFlag: canonical.filterFlag,
    simpleFilters:
      Object.keys(canonical.simpleFilters).length > 0
        ? (encodeSimpleFiltersForView(
            canonical.simpleFilters,
            currentUserId,
          ) as DocumentViewQueryState["simpleFilters"])
        : null,
  };
}

export function variantForSimpleFilter(id: string): FilterVariant | null {
  return DOCUMENTS_SIMPLE_FILTERS[id] ?? null;
}
