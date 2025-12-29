import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceRuns, buildRunRecord, runsKeys, RUNS_PAGE_SIZE } from "../data";
import { buildCounts, buildCreatedAtRange, filterRuns } from "../utils";
import type { RunsFilters } from "../types";
import { DEFAULT_RUNS_FILTERS } from "../constants";

export function useRunsModel({ workspaceId, initialFilters }: { workspaceId: string; initialFilters?: RunsFilters }) {
  const [filters, setFilters] = useState<RunsFilters>(initialFilters ?? DEFAULT_RUNS_FILTERS);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const query = useMemo(() => {
    const dateRange = buildCreatedAtRange(filters.dateRange);
    return {
      page: 1,
      page_size: RUNS_PAGE_SIZE,
      include_total: true,
      q: filters.search || undefined,
      sort: "-created_at",
      ...dateRange,
    };
  }, [filters.dateRange, filters.search]);

  const runsQuery = useQuery({
    queryKey: runsKeys.list(workspaceId, query),
    queryFn: ({ signal }) => fetchWorkspaceRuns(workspaceId, query, signal),
    enabled: Boolean(workspaceId),
    staleTime: 15_000,
  });

  const runs = useMemo(
    () => (runsQuery.data?.items ?? []).map((run) => buildRunRecord(run)),
    [runsQuery.data?.items],
  );
  const visibleRuns = useMemo(() => filterRuns(runs, filters), [filters, runs]);
  const counts = useMemo(() => buildCounts(runs), [runs]);
  const configOptions = useMemo(
    () =>
      Array.from(
        new Set(runs.map((run) => run.configLabel).filter((value) => value && value !== "—")),
      ).sort(),
    [runs],
  );
  const ownerOptions = useMemo(
    () =>
      Array.from(
        new Set(runs.map((run) => run.ownerLabel).filter((value) => value && value !== "—")),
      ).sort(),
    [runs],
  );
  const supportsResultFilters = useMemo(
    () => runs.some((run) => run.warnings !== null || run.errors !== null),
    [runs],
  );

  const activeRun = useMemo(
    () => (activeId ? runs.find((run) => run.id === activeId) ?? null : null),
    [activeId, runs],
  );

  const updateFilters = useCallback((next: Partial<RunsFilters>) => {
    setFilters((current) => ({ ...current, ...next }));
  }, []);

  const setFiltersAll = useCallback((next: RunsFilters) => {
    setFilters(next);
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_RUNS_FILTERS);
  }, []);

  const openPreview = useCallback((id: string) => {
    setActiveId(id);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => {
    setPreviewOpen(false);
  }, []);

  const togglePreview = useCallback(
    (id: string) => {
      if (previewOpen && activeId === id) {
        setPreviewOpen(false);
        return;
      }
      setActiveId(id);
      setPreviewOpen(true);
    },
    [activeId, previewOpen],
  );

  return {
    state: {
      filters,
      activeId,
      previewOpen,
    },
    derived: {
      runs,
      visibleRuns,
      counts,
      configOptions,
      ownerOptions,
      activeRun,
      supportsResultFilters,
      isLoading: runsQuery.isLoading,
      isError: runsQuery.isError,
      totalCount: runsQuery.data?.total ?? runsQuery.data?.items?.length ?? 0,
    },
    actions: {
      updateFilters,
      setFilters: setFiltersAll,
      resetFilters,
      openPreview,
      closePreview,
      togglePreview,
      setActiveId,
      refetch: runsQuery.refetch,
    },
  };
}

export type RunsModel = ReturnType<typeof useRunsModel>;
