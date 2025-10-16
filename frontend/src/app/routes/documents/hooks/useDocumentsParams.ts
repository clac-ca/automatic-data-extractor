import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { useDebouncedValue } from "../../../../shared/hooks/useDebouncedValue";
import type { DocumentsQueryParams } from "../../../../features/documents/api";

export const DEFAULT_SORT_PARAM = "-created_at";
const DEFAULT_PAGE = 1;
const DEFAULT_PER_PAGE = 50;
const DEBOUNCE_MS = 300;

type MaybeMe = "me" | null;

export interface DocumentsUrlState {
  status: string[];
  source: string[];
  tags: string[];
  uploader: MaybeMe;
  uploaderIds: string[];
  q: string;
  createdFrom?: string;
  createdTo?: string;
  lastRunFrom?: string;
  lastRunTo?: string;
  sort: string;
  page: number;
  perPage: number;
  includeTotal: boolean;
}

const EMPTY_STATE: DocumentsUrlState = {
  status: [],
  source: [],
  tags: [],
  uploader: null,
  uploaderIds: [],
  q: "",
  sort: DEFAULT_SORT_PARAM,
  page: DEFAULT_PAGE,
  perPage: DEFAULT_PER_PAGE,
  includeTotal: false,
};

function parseInteger(value: string | null, fallback: number) {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) || parsed <= 0 ? fallback : parsed;
}

function uniqueSorted(values: readonly string[]) {
  return Array.from(new Set(values.filter((value) => value.trim().length > 0))).sort();
}

export function parseDocumentsSearchParams(searchParams: URLSearchParams): DocumentsUrlState {
  const status = uniqueSorted(searchParams.getAll("status"));
  const source = uniqueSorted(searchParams.getAll("source"));
  const tags = uniqueSorted(searchParams.getAll("tag"));
  const uploaderIds = uniqueSorted(searchParams.getAll("uploader_id"));
  const uploader = searchParams.get("uploader") === "me" ? "me" : null;
  const q = searchParams.get("q") ?? "";
  const createdFrom = searchParams.get("created_from") ?? undefined;
  const createdTo = searchParams.get("created_to") ?? undefined;
  const lastRunFrom = searchParams.get("last_run_from") ?? undefined;
  const lastRunTo = searchParams.get("last_run_to") ?? undefined;
  const sort = searchParams.get("sort") ?? DEFAULT_SORT_PARAM;
  const page = parseInteger(searchParams.get("page"), DEFAULT_PAGE);
  const perPage = parseInteger(searchParams.get("per_page"), DEFAULT_PER_PAGE);
  const includeTotal = searchParams.get("include_total") === "true";

  return {
    status,
    source,
    tags,
    uploader,
    uploaderIds,
    q,
    createdFrom,
    createdTo,
    lastRunFrom,
    lastRunTo,
    sort,
    page,
    perPage,
    includeTotal,
  };
}

export function serialiseDocumentsSearchParams(state: DocumentsUrlState) {
  const params = new URLSearchParams();

  for (const value of state.status) {
    params.append("status", value);
  }
  for (const value of state.source) {
    params.append("source", value);
  }
  for (const value of state.tags) {
    params.append("tag", value);
  }
  for (const value of state.uploaderIds) {
    params.append("uploader_id", value);
  }

  if (state.uploader === "me") {
    params.set("uploader", "me");
  }
  if (state.q.trim().length > 0) {
    params.set("q", state.q.trim());
  }
  if (state.createdFrom) {
    params.set("created_from", state.createdFrom);
  }
  if (state.createdTo) {
    params.set("created_to", state.createdTo);
  }
  if (state.lastRunFrom) {
    params.set("last_run_from", state.lastRunFrom);
  }
  if (state.lastRunTo) {
    params.set("last_run_to", state.lastRunTo);
  }
  if (state.sort !== DEFAULT_SORT_PARAM) {
    params.set("sort", state.sort);
  }
  if (state.page !== DEFAULT_PAGE) {
    params.set("page", state.page.toString());
  }
  if (state.perPage !== DEFAULT_PER_PAGE) {
    params.set("per_page", state.perPage.toString());
  }
  if (state.includeTotal) {
    params.set("include_total", "true");
  }

  return params;
}

export function useDocumentsParams() {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlState = useMemo(
    () => ({ ...EMPTY_STATE, ...parseDocumentsSearchParams(searchParams) }),
    [searchParams],
  );
  const debouncedQuery = useDebouncedValue(urlState.q, DEBOUNCE_MS);

  const apiParams: DocumentsQueryParams = useMemo(
    () => ({
      status: urlState.status,
      source: urlState.source,
      tag: urlState.tags,
      uploader: urlState.uploader ?? undefined,
      uploader_id: urlState.uploaderIds,
      q: debouncedQuery.trim().length > 0 ? debouncedQuery.trim() : undefined,
      created_from: urlState.createdFrom,
      created_to: urlState.createdTo,
      last_run_from: urlState.lastRunFrom,
      last_run_to: urlState.lastRunTo,
      sort: urlState.sort,
      page: urlState.page,
      per_page: urlState.perPage,
      include_total: urlState.includeTotal,
    }),
    [
      debouncedQuery,
      urlState.createdFrom,
      urlState.createdTo,
      urlState.includeTotal,
      urlState.lastRunFrom,
      urlState.lastRunTo,
      urlState.page,
      urlState.perPage,
      urlState.sort,
      urlState.source,
      urlState.status,
      urlState.tags,
      urlState.uploader,
      urlState.uploaderIds,
    ],
  );

  const applyState = useCallback(
    (next: DocumentsUrlState) => {
      const params = serialiseDocumentsSearchParams(next);
      setSearchParams(params, { replace: true });
    },
    [setSearchParams],
  );

  const resetPage = useCallback(
    (next: DocumentsUrlState) => ({ ...next, page: DEFAULT_PAGE }),
    [],
  );

  const setStatuses = useCallback(
    (values: string[]) => {
      applyState(resetPage({ ...urlState, status: uniqueSorted(values) }));
    },
    [applyState, resetPage, urlState],
  );

  const setTags = useCallback(
    (values: string[]) => {
      applyState(resetPage({ ...urlState, tags: uniqueSorted(values) }));
    },
    [applyState, resetPage, urlState],
  );

  const addTag = useCallback(
    (value: string) => {
      if (!value.trim()) {
        return;
      }
      const tags = uniqueSorted([...urlState.tags, value.trim()]);
      applyState(resetPage({ ...urlState, tags }));
    },
    [applyState, resetPage, urlState],
  );

  const removeTag = useCallback(
    (value: string) => {
      const tags = urlState.tags.filter((tag) => tag !== value);
      applyState(resetPage({ ...urlState, tags }));
    },
    [applyState, resetPage, urlState],
  );

  const setUploader = useCallback(
    (value: MaybeMe) => {
      applyState(resetPage({ ...urlState, uploader: value }));
    },
    [applyState, resetPage, urlState],
  );

  const setSearch = useCallback(
    (value: string) => {
      applyState(resetPage({ ...urlState, q: value }));
    },
    [applyState, resetPage, urlState],
  );

  const setSort = useCallback(
    (value: string) => {
      applyState(resetPage({ ...urlState, sort: value }));
    },
    [applyState, resetPage, urlState],
  );

  const setPage = useCallback(
    (value: number) => {
      const page = value < 1 ? DEFAULT_PAGE : value;
      applyState({ ...urlState, page });
    },
    [applyState, urlState],
  );

  const setPerPage = useCallback(
    (value: number) => {
      const perPage = value < 1 ? DEFAULT_PER_PAGE : value;
      applyState(resetPage({ ...urlState, perPage }));
    },
    [applyState, resetPage, urlState],
  );

  const setCreatedRange = useCallback(
    (from?: string, to?: string) => {
      applyState(
        resetPage({
          ...urlState,
          createdFrom: from || undefined,
          createdTo: to || undefined,
        }),
      );
    },
    [applyState, resetPage, urlState],
  );

  const setLastRunRange = useCallback(
    (from?: string, to?: string) => {
      applyState(
        resetPage({
          ...urlState,
          lastRunFrom: from || undefined,
          lastRunTo: to || undefined,
        }),
      );
    },
    [applyState, resetPage, urlState],
  );

  const clearFilters = useCallback(() => {
    applyState({ ...EMPTY_STATE });
  }, [applyState]);

  return {
    urlState,
    apiParams,
    setStatuses,
    setTags,
    addTag,
    removeTag,
    setUploader,
    setSearch,
    setSort,
    setPage,
    setPerPage,
    setCreatedRange,
    setLastRunRange,
    clearFilters,
  };
}
