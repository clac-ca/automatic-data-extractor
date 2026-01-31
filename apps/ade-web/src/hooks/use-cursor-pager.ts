import { useCallback, useEffect, useRef } from "react";

import type { CursorPage } from "@/api/pagination";

type CursorFetchOptions = {
  cursor: string | null;
  limit: number;
  includeTotal: boolean;
  signal?: AbortSignal;
};

type CursorFetcher<T> = (options: CursorFetchOptions) => Promise<CursorPage<T>>;

type UseCursorPagerOptions<T> = {
  page: number;
  limit: number;
  includeTotal: boolean;
  resetKey: string;
  fetchPage: CursorFetcher<T>;
};

export function useCursorPager<T>({
  page,
  limit,
  includeTotal,
  resetKey,
  fetchPage,
}: UseCursorPagerOptions<T>) {
  const cursorByPageRef = useRef<Map<number, string | null>>(new Map([[1, null]]));

  useEffect(() => {
    cursorByPageRef.current = new Map([[1, null]]);
  }, [resetKey, limit]);

  const fetchCurrentPage = useCallback(
    async (signal?: AbortSignal) => {
      const cursorByPage = cursorByPageRef.current;
      if (!cursorByPage.has(1)) {
        cursorByPage.set(1, null);
      }

      const targetPage = Math.max(1, page);
      const knownCursor = cursorByPage.get(targetPage);

      if (knownCursor !== undefined) {
        const data = await fetchPage({
          cursor: knownCursor ?? null,
          limit,
          includeTotal,
          signal,
        });
        cursorByPage.set(targetPage + 1, data.meta.nextCursor ?? null);
        return data;
      }

      const knownPages = Array.from(cursorByPage.keys())
        .filter((entry) => entry < targetPage)
        .sort((left, right) => right - left);
      let currentPage = knownPages[0] ?? 1;
      let cursor = cursorByPage.get(currentPage) ?? null;
      let lastData: CursorPage<T> | null = null;

      while (currentPage < targetPage) {
        lastData = await fetchPage({
          cursor,
          limit,
          includeTotal: false,
          signal,
        });
        const nextCursor = lastData.meta.nextCursor ?? null;
        cursorByPage.set(currentPage + 1, nextCursor);
        if (!nextCursor) {
          return lastData;
        }
        cursor = nextCursor;
        currentPage += 1;
      }

      const data = await fetchPage({ cursor, limit, includeTotal, signal });
      cursorByPage.set(targetPage + 1, data.meta.nextCursor ?? null);
      return data;
    },
    [fetchPage, includeTotal, limit, page],
  );

  return { fetchCurrentPage };
}
