import { useMemo } from "react";

export const MAX_PAGE_SIZE = 100;
export const DEFAULT_PAGE_SIZE = 50;

export function clampPageSize(size?: number): number | undefined {
  if (typeof size !== "number" || Number.isNaN(size) || size <= 0) {
    return undefined;
  }
  return Math.min(size, MAX_PAGE_SIZE);
}

export type PaginatedPage<T> = {
  readonly items: T[];
  readonly page: number;
  readonly page_size: number;
  readonly has_next: boolean;
  readonly has_previous: boolean;
  readonly total?: number | null;
};

export async function collectAllPages<T>(
  fetchPage: (page: number) => Promise<PaginatedPage<T>>,
  options: { readonly maxPages?: number } = {},
): Promise<PaginatedPage<T>> {
  const { maxPages = 50 } = options;
  const pages: PaginatedPage<T>[] = [];
  let combined: T[] = [];
  let total: number | null | undefined;

  for (let page = 1; page <= maxPages; page += 1) {
    const pageData = await fetchPage(page);
    pages.push(pageData);
    combined = combined.concat(pageData.items ?? []);
    if (total === undefined && pageData.total !== undefined) {
      total = pageData.total ?? null;
    }
    if (!pageData.has_next) {
      break;
    }
  }

  const last = pages.at(-1);
  const first = pages.at(0);

  if (!last || !first) {
    throw new Error("No pages were returned while collecting pagination results.");
  }

  return {
    ...last,
    items: combined,
    page: 1,
    page_size: first.page_size,
    has_next: false,
    has_previous: false,
    total: total ?? last.total,
  };
}

type PageWithItems<T> = {
  readonly items?: readonly T[] | null;
};

export function useFlattenedPages<T>(
  pages: readonly PageWithItems<T>[] | undefined,
  getKey: (item: T) => string,
) {
  return useMemo(() => {
    if (!pages || pages.length === 0) {
      return [] as T[];
    }

    const combined: T[] = [];
    const indexByKey = new Map<string, number>();

    for (const page of pages) {
      const pageItems = Array.isArray(page.items) ? (page.items as readonly T[]) : [];
      for (const item of pageItems) {
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
