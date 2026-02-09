import { useMemo } from "react";

export const MAX_PAGE_SIZE = 200;
export const DEFAULT_PAGE_SIZE = 50;

export function clampPageSize(size?: number): number | undefined {
  if (typeof size !== "number" || Number.isNaN(size) || size <= 0) {
    return undefined;
  }
  return Math.min(size, MAX_PAGE_SIZE);
}

export type CursorMeta = {
  readonly limit: number;
  readonly hasMore: boolean;
  readonly nextCursor: string | null;
  readonly totalIncluded: boolean;
  readonly totalCount: number | null;
  readonly changesCursor?: string | null;
};

export type CursorPage<T> = {
  readonly items?: readonly T[] | null;
  readonly meta: CursorMeta;
  readonly facets?: Record<string, unknown> | null;
};

export async function collectAllPages<T>(
  fetchPage: (cursor: string | null) => Promise<CursorPage<T>>,
  options: { readonly maxPages?: number } = {},
): Promise<CursorPage<T>> {
  const { maxPages = 50 } = options;
  const pages: CursorPage<T>[] = [];
  let combined: T[] = [];
  let cursor: string | null = null;

  for (let page = 0; page < maxPages; page += 1) {
    const pageData = await fetchPage(cursor);
    pages.push(pageData);
    combined = combined.concat(pageData.items ?? []);
    if (!pageData.meta.hasMore) {
      break;
    }
    cursor = pageData.meta.nextCursor ?? null;
    if (!cursor) {
      break;
    }
  }

  const last = pages.at(-1);

  if (!last) {
    throw new Error("No pages were returned while collecting pagination results.");
  }

  return {
    ...last,
    items: combined,
    meta: {
      ...last.meta,
      hasMore: false,
      nextCursor: null,
    },
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
