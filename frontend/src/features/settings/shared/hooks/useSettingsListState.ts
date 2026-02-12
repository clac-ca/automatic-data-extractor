import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import type { SettingsListState, SettingsSortOrder } from "../types";

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 25;

function parsePositiveInt(value: string | null, fallback: number) {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function parseSortOrder(value: string | null, fallback: SettingsSortOrder): SettingsSortOrder {
  return value === "asc" || value === "desc" ? value : fallback;
}

export interface UseSettingsListStateOptions {
  readonly defaults?: Partial<Pick<SettingsListState, "q" | "sort" | "order" | "page" | "pageSize">>;
  readonly filterKeys?: readonly string[];
}

function applySearchPatch(
  current: URLSearchParams,
  patch: Record<string, string | null | undefined>,
  preservePage = true,
) {
  const next = new URLSearchParams(current);

  for (const [key, value] of Object.entries(patch)) {
    const normalized = value?.trim() ?? "";
    if (!normalized) {
      next.delete(key);
      continue;
    }
    next.set(key, normalized);
  }

  if (!preservePage) {
    next.delete("page");
  }

  return next;
}

export function useSettingsListState({ defaults, filterKeys = [] }: UseSettingsListStateOptions = {}) {
  const [searchParams, setSearchParams] = useSearchParams();

  const state = useMemo<SettingsListState>(() => {
    const filters = Object.fromEntries(
      filterKeys
        .map((key) => [key, searchParams.get(key)?.trim() ?? ""])
        .filter(([, value]) => value.length > 0),
    );

    return {
      q: searchParams.get("q")?.trim() ?? defaults?.q ?? "",
      sort: searchParams.get("sort")?.trim() ?? defaults?.sort ?? "",
      order: parseSortOrder(searchParams.get("order"), defaults?.order ?? "asc"),
      page: parsePositiveInt(searchParams.get("page"), defaults?.page ?? DEFAULT_PAGE),
      pageSize: parsePositiveInt(searchParams.get("pageSize"), defaults?.pageSize ?? DEFAULT_PAGE_SIZE),
      filters,
    };
  }, [defaults?.order, defaults?.page, defaults?.pageSize, defaults?.q, defaults?.sort, filterKeys, searchParams]);

  const setQuery = useCallback(
    (q: string) => {
      setSearchParams((current) => applySearchPatch(current, { q }, false), { replace: true });
    },
    [setSearchParams],
  );

  const setSort = useCallback(
    (sort: string, order: SettingsSortOrder) => {
      setSearchParams((current) => applySearchPatch(current, { sort, order }, false), { replace: true });
    },
    [setSearchParams],
  );

  const setPage = useCallback(
    (page: number) => {
      const normalized = page > 1 ? String(Math.floor(page)) : null;
      setSearchParams((current) => applySearchPatch(current, { page: normalized }, true), { replace: true });
    },
    [setSearchParams],
  );

  const setPageSize = useCallback(
    (pageSize: number) => {
      const normalized = pageSize > 0 ? String(Math.floor(pageSize)) : String(DEFAULT_PAGE_SIZE);
      setSearchParams((current) => applySearchPatch(current, { pageSize: normalized }, false), { replace: true });
    },
    [setSearchParams],
  );

  const setFilter = useCallback(
    (filterKey: string, value: string | null) => {
      setSearchParams((current) => applySearchPatch(current, { [filterKey]: value }, false), { replace: true });
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const key of filterKeys) {
          next.delete(key);
        }
        next.delete("page");
        return next;
      },
      { replace: true },
    );
  }, [filterKeys, setSearchParams]);

  const queryString = useMemo(() => {
    const value = searchParams.toString();
    return value.length > 0 ? `?${value}` : "";
  }, [searchParams]);

  const withCurrentSearch = useCallback(
    (path: string) => {
      const value = searchParams.toString();
      return value.length > 0 ? `${path}?${value}` : path;
    },
    [searchParams],
  );

  return {
    state,
    setQuery,
    setSort,
    setPage,
    setPageSize,
    setFilter,
    clearFilters,
    queryString,
    withCurrentSearch,
  };
}
