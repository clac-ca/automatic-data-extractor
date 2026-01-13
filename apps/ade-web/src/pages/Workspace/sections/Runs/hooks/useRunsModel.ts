import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchRunColumns, fetchRunFields, fetchRunMetrics, fetchWorkspaceRuns } from "@api/runs/api";
import type { RunsQuery } from "@api/runs/api";
import { runsKeys } from "@hooks/runs/keys";
import { buildCounts, buildRunRecord } from "../utils";

export function useRunsModel({ workspaceId, query }: { workspaceId: string; query: RunsQuery }) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

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
      activeId,
      previewOpen,
    },
    derived: {
      runs,
      visibleRuns: runs,
      counts,
      activeRun,
      isLoading: runsQuery.isLoading,
      isError: runsQuery.isError,
      totalCount: runsQuery.data?.total ?? runsQuery.data?.items?.length ?? 0,
      pageCount: runsQuery.data?.pageCount ?? 0,
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
      openPreview,
      closePreview,
      togglePreview,
      setActiveId,
      refetch: runsQuery.refetch,
    },
  };
}

export type RunsModel = ReturnType<typeof useRunsModel>;
