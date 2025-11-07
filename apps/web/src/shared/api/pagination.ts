import { useMemo } from "react";

export interface PaginatedResult<T> {
  readonly items: readonly T[];
  readonly page: number;
  readonly pageSize: number;
  readonly hasNext: boolean;
  readonly hasPrevious: boolean;
  readonly total: number | null;
}

export type PaginatedWireResponse<T> = {
  readonly items?: readonly T[] | null;
  readonly page?: number | null;
  readonly page_size?: number | null;
  readonly per_page?: number | null;
  readonly has_next?: boolean | null;
  readonly has_previous?: boolean | null;
  readonly total?: number | null;
};

export function normalizePaginatedResponse<T>(
  response: PaginatedWireResponse<T> | null | undefined,
): PaginatedResult<T> {
  const items = Array.isArray(response?.items) ? (response?.items as readonly T[]) : [];
  const page = typeof response?.page === "number" && response.page > 0 ? response.page : 1;
  const pageSizeCandidate =
    typeof response?.page_size === "number" && response.page_size > 0
      ? response.page_size
      : typeof response?.per_page === "number" && response.per_page > 0
        ? response.per_page
        : items.length;
  const hasNext = Boolean(response?.has_next);
  const hasPrevious = response?.has_previous ?? page > 1;
  const total = typeof response?.total === "number" && response.total >= 0 ? response.total : null;

  return {
    items,
    page,
    pageSize: pageSizeCandidate,
    hasNext,
    hasPrevious,
    total,
  };
}

export function useFlattenedPages<T>(
  pages: readonly PaginatedResult<T>[] | undefined,
  getKey: (item: T) => string,
) {
  return useMemo(() => {
    if (!pages || pages.length === 0) {
      return [] as T[];
    }

    const combined: T[] = [];
    const indexByKey = new Map<string, number>();

    for (const page of pages) {
      for (const item of page.items) {
        const key = getKey(item);
        const existingIndex = indexByKey.get(key);

        if (existingIndex === undefined) {
          indexByKey.set(key, combined.length);
          combined.push(item);
          continue;
        }

        combined[existingIndex] = item;
      }
    }

    return combined;
  }, [pages, getKey]);
}
