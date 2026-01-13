import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchRunColumns, fetchRunFields, fetchRunMetrics, fetchWorkspaceRuns } from "@api/runs/api";
import type { RunsQuery } from "@api/runs/api";
import { runsKeys } from "@hooks/runs/keys";

import { buildCounts, buildRunRecord } from "../utils";
import type { RunRecord } from "../types";

export function useRunsView({
  workspaceId,
  page,
  perPage,
  sort,
  filters,
  joinOperator,
  activeRunId,
  enabled = true,
}: {
  workspaceId: string;
  page: number;
  perPage: number;
  sort: string | null;
  filters: RunsQuery["filters"] | null;
  joinOperator: RunsQuery["joinOperator"] | null;
  activeRunId: string | null;
  enabled?: boolean;
}) {
  const query = useMemo<RunsQuery>(
    () => ({
      page,
      perPage,
      sort: sort ?? null,
      filters: filters ?? undefined,
      joinOperator: joinOperator ?? undefined,
    }),
    [page, perPage, sort, filters, joinOperator],
  );

  const runsQuery = useQuery({
    queryKey: runsKeys.list(workspaceId, query),
    queryFn: ({ signal }) => fetchWorkspaceRuns(workspaceId, query, signal),
    enabled: enabled && Boolean(workspaceId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });

  const runs = useMemo<RunRecord[]>(
    () => (runsQuery.data?.items ?? []).map((run) => buildRunRecord(run)),
    [runsQuery.data?.items],
  );

  const counts = useMemo(() => buildCounts(runs), [runs]);

  const activeRun = useMemo(
    () => (activeRunId ? runs.find((run) => run.id === activeRunId) ?? null : null),
    [activeRunId, runs],
  );

  const shouldFetchDetails = Boolean(activeRunId && activeRun);
  const shouldPollDetails =
    activeRun?.status === "running" || activeRun?.status === "queued";

  const metricsQuery = useQuery({
    queryKey: activeRunId ? runsKeys.metrics(activeRunId) : [...runsKeys.root(), "metrics", "none"],
    queryFn: ({ signal }) => (activeRunId ? fetchRunMetrics(activeRunId, signal) : Promise.resolve(null)),
    enabled: shouldFetchDetails,
    staleTime: 30_000,
    refetchInterval: shouldPollDetails ? 10_000 : false,
  });

  const fieldsQuery = useQuery({
    queryKey: activeRunId ? runsKeys.fields(activeRunId) : [...runsKeys.root(), "fields", "none"],
    queryFn: ({ signal }) => (activeRunId ? fetchRunFields(activeRunId, signal) : Promise.resolve(null)),
    enabled: shouldFetchDetails,
    staleTime: 30_000,
    refetchInterval: shouldPollDetails ? 10_000 : false,
  });

  const columnsQuery = useQuery({
    queryKey: activeRunId ? runsKeys.columns(activeRunId, null) : [...runsKeys.root(), "columns", "none"],
    queryFn: ({ signal }) => (activeRunId ? fetchRunColumns(activeRunId, null, signal) : Promise.resolve(null)),
    enabled: shouldFetchDetails,
    staleTime: 30_000,
    refetchInterval: shouldPollDetails ? 10_000 : false,
  });

  return {
    runs,
    counts,
    activeRun,
    pageCount: runsQuery.data?.pageCount ?? 1,
    totalCount: runsQuery.data?.total ?? runsQuery.data?.items?.length ?? 0,
    isLoading: runsQuery.isLoading,
    isFetching: runsQuery.isFetching,
    isError: runsQuery.isError,
    error: runsQuery.error instanceof Error ? runsQuery.error.message : null,
    metrics: metricsQuery.data ?? null,
    metricsLoading: metricsQuery.isLoading,
    metricsError: metricsQuery.isError,
    fields: fieldsQuery.data ?? null,
    fieldsLoading: fieldsQuery.isLoading,
    fieldsError: fieldsQuery.isError,
    columns: columnsQuery.data ?? null,
    columnsLoading: columnsQuery.isLoading,
    columnsError: columnsQuery.isError,
    refetch: runsQuery.refetch,
  };
}
