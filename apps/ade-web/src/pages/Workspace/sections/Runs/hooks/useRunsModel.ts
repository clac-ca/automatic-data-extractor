import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchRunColumns, fetchRunFields, fetchRunMetrics, fetchWorkspaceRuns, RUNS_PAGE_SIZE } from "@api/runs/api";
import { runsKeys } from "@hooks/runs/keys";
import { buildCounts, buildCreatedAtRange, buildRunRecord } from "../utils";
import type { RunConfigOption, RunsFilters } from "../types";
import { DEFAULT_RUNS_FILTERS } from "../constants";

export function useRunsModel({ workspaceId, initialFilters }: { workspaceId: string; initialFilters?: RunsFilters }) {
  const [filters, setFilters] = useState<RunsFilters>(initialFilters ?? DEFAULT_RUNS_FILTERS);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const query = useMemo(() => {
    const dateRange = buildCreatedAtRange(filters.dateRange);
    const trimmedSearch = filters.search.trim();
    return {
      page: 1,
      page_size: RUNS_PAGE_SIZE,
      include_total: true,
      q: trimmedSearch.length >= 2 ? trimmedSearch : undefined,
      status: filters.status !== "all" ? filters.status : undefined,
      configuration_id: filters.configurationId ?? undefined,
      sort: "-created_at",
      ...dateRange,
    };
  }, [filters.configurationId, filters.dateRange, filters.search, filters.status]);

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
  const counts = useMemo(() => buildCounts(runs), [runs]);
  const configOptions = useMemo<RunConfigOption[]>(() => {
    const options = new Map<string, string>();
    runs.forEach((run) => {
      if (!run.configurationId) return;
      const label = run.configLabel && run.configLabel !== "—" ? run.configLabel : run.configurationId;
      options.set(run.configurationId, label);
    });
    return Array.from(options, ([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label));
  }, [runs]);

  const activeRun = useMemo(
    () => (activeId ? runs.find((run) => run.id === activeId) ?? null : null),
    [activeId, runs],
  );

  const shouldFetchDetails = Boolean(activeId && previewOpen);
  const shouldPollDetails =
    previewOpen && activeRun ? activeRun.status === "running" || activeRun.status === "queued" : false;

  const metricsQuery = useQuery({
    queryKey: activeId ? runsKeys.metrics(activeId) : [...runsKeys.root(), "metrics", "none"],
    queryFn: ({ signal }) => (activeId ? fetchRunMetrics(activeId, signal) : Promise.resolve(null)),
    enabled: shouldFetchDetails,
    staleTime: 30_000,
    refetchInterval: shouldPollDetails ? 10_000 : false,
  });

  const fieldsQuery = useQuery({
    queryKey: activeId ? runsKeys.fields(activeId) : [...runsKeys.root(), "fields", "none"],
    queryFn: ({ signal }) => (activeId ? fetchRunFields(activeId, signal) : Promise.resolve(null)),
    enabled: shouldFetchDetails,
    staleTime: 30_000,
    refetchInterval: shouldPollDetails ? 10_000 : false,
  });

  const columnsQuery = useQuery({
    queryKey: activeId ? runsKeys.columns(activeId, null) : [...runsKeys.root(), "columns", "none"],
    queryFn: ({ signal }) => (activeId ? fetchRunColumns(activeId, null, signal) : Promise.resolve(null)),
    enabled: shouldFetchDetails,
    staleTime: 30_000,
    refetchInterval: shouldPollDetails ? 10_000 : false,
  });

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
      visibleRuns: runs,
      counts,
      configOptions,
      activeRun,
      isLoading: runsQuery.isLoading,
      isError: runsQuery.isError,
      totalCount: runsQuery.data?.total ?? runsQuery.data?.items?.length ?? 0,
      metrics: metricsQuery.data ?? null,
      metricsLoading: metricsQuery.isLoading,
      metricsError: metricsQuery.isError,
      fields: fieldsQuery.data ?? null,
      fieldsLoading: fieldsQuery.isLoading,
      fieldsError: fieldsQuery.isError,
      columns: columnsQuery.data ?? null,
      columnsLoading: columnsQuery.isLoading,
      columnsError: columnsQuery.isError,
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
