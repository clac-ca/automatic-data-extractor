import { parseAsInteger, parseAsString, parseAsStringEnum } from "nuqs";

import { getValidFilters } from "@/lib/data-table";
import { getFiltersStateParser, getSortingStateParser } from "@/lib/parsers";
import type { FilterItem, FilterJoinOperator } from "@/api/listing";
import type { ExtendedColumnFilter, ExtendedColumnSort } from "@/types/data-table";
import type { components } from "@/types";

import {
  DEFAULT_PAGE_SIZE,
  DOCUMENTS_FILTER_IDS,
  DOCUMENTS_SORT_IDS,
} from "../../shared/constants";
import type { DocumentListRow } from "../../shared/types";

type SortState = ExtendedColumnSort<DocumentListRow>[];
type FiltersState = ExtendedColumnFilter<DocumentListRow>[];
type FilterValue = ExtendedColumnFilter<DocumentListRow>["value"];
type JoinOperator = "and" | "or";
type Lifecycle = "active" | "deleted";
type DocumentViewQueryState = components["schemas"]["DocumentViewQueryState"];

type QuerySnapshotInput = {
  q: string | null;
  sort: unknown;
  filters: unknown;
  joinOperator: unknown;
  lifecycle: unknown;
};

export type DocumentsQuerySnapshot = {
  q: string | null;
  sort: SortState;
  filters: FiltersState;
  joinOperator: JoinOperator;
  lifecycle: Lifecycle;
};

export const documentsPageParser = parseAsInteger.withDefault(1);
export const documentsPerPageParser = parseAsInteger.withDefault(DEFAULT_PAGE_SIZE);
export const documentsViewIdParser = parseAsString;
export const documentsSortParser = getSortingStateParser<DocumentListRow>(DOCUMENTS_SORT_IDS);
export const documentsFiltersParser = getFiltersStateParser<DocumentListRow>(DOCUMENTS_FILTER_IDS);
export const documentsJoinOperatorParser = parseAsStringEnum(["and", "or"])
  .withOptions({ clearOnDefault: true })
  .withDefault("and");
export const documentsLifecycleParser = parseAsStringEnum(["active", "deleted"])
  .withOptions({ clearOnDefault: true })
  .withDefault("active");
export const documentsSearchParser = parseAsString;

export const documentsQueryParsers = {
  q: documentsSearchParser,
  sort: documentsSortParser,
  filters: documentsFiltersParser,
  joinOperator: documentsJoinOperatorParser,
  lifecycle: documentsLifecycleParser,
};

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

function normalizeJoinOperator(value: unknown): JoinOperator {
  return value === "or" ? "or" : "and";
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
    lifecycle: normalizeLifecycle(input.lifecycle),
  };
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

export function resolveListFiltersForApi({
  snapshot,
  currentUserId,
}: {
  snapshot: DocumentsQuerySnapshot;
  currentUserId: string | null;
}): { filters: FilterItem[] | null; joinOperator: FilterJoinOperator | null } {
  if (!snapshot.filters.length) {
    return {
      filters: null,
      joinOperator: null,
    };
  }

  const parsed = getValidFilters(snapshot.filters).map((filter) => {
    if (filter.id !== "assigneeId") return filter;
    const next = Array.isArray(filter.value)
      ? filter.value.map((value) => resolveAssigneeTokenValue(value, currentUserId))
      : resolveAssigneeToken(filter.value, currentUserId);
    return { ...filter, value: next };
  });

  return {
    filters: parsed.length ? toApiFilters(parsed) : null,
    joinOperator: parsed.length ? (snapshot.joinOperator as FilterJoinOperator) : null,
  };
}

export function hasExplicitListState(snapshot: DocumentsQuerySnapshot): boolean {
  return Boolean(
    snapshot.q ||
      snapshot.sort.length > 0 ||
      snapshot.filters.length > 0 ||
      snapshot.joinOperator === "or" ||
      snapshot.lifecycle === "deleted",
  );
}

export function canonicalizeSnapshotForViewPersistence(
  snapshot: DocumentsQuerySnapshot,
): DocumentsQuerySnapshot {
  if (!snapshot.filters.length) {
    return {
      ...snapshot,
      joinOperator: "and",
    };
  }
  return snapshot;
}

export function parseViewQueryStateToSnapshot(
  queryState: Record<string, unknown> | null | undefined,
): DocumentsQuerySnapshot {
  const value = queryState ?? {};

  return buildDocumentsQuerySnapshot({
    q: typeof value.q === "string" ? value.q : null,
    sort: value.sort,
    filters: value.filters,
    joinOperator: value.joinOperator,
    lifecycle: value.lifecycle,
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
  };
}
