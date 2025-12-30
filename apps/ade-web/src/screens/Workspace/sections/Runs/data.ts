import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { components, paths, RunResource } from "@schema";

import type { RunRecord, RunsQuery } from "./types";
import { formatDuration, formatTimestamp } from "./utils";

type RunColumnsQuery = paths["/api/v1/runs/{run_id}/columns"]["get"]["parameters"]["query"];
type RunPage = components["schemas"]["RunPage"];
type RunMetricsResource = components["schemas"]["RunMetricsResource"];
type RunFieldResource = components["schemas"]["RunFieldResource"];
type RunColumnResource = components["schemas"]["RunColumnResource"];

export const RUNS_PAGE_SIZE = 50;

export const runsKeys = {
  root: () => ["runs"] as const,
  workspace: (workspaceId: string) => [...runsKeys.root(), workspaceId] as const,
  list: (workspaceId: string, query: RunsQuery) => [...runsKeys.workspace(workspaceId), "list", query] as const,
  run: (runId: string) => [...runsKeys.root(), "run", runId] as const,
  metrics: (runId: string) => [...runsKeys.run(runId), "metrics"] as const,
  fields: (runId: string) => [...runsKeys.run(runId), "fields"] as const,
  columns: (runId: string, query: RunColumnsQuery | null) => [...runsKeys.run(runId), "columns", query ?? {}] as const,
};

export async function fetchWorkspaceRuns(
  workspaceId: string,
  query: RunsQuery,
  signal?: AbortSignal,
): Promise<RunPage> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/runs", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });
  if (!data) throw new Error("Expected run page payload.");
  return data;
}

export async function fetchRunMetrics(runId: string, signal?: AbortSignal): Promise<RunMetricsResource | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{run_id}/metrics", {
      params: { path: { run_id: runId } },
      signal,
    });
    if (!data) {
      throw new Error("Expected run metrics payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchRunFields(runId: string, signal?: AbortSignal): Promise<RunFieldResource[] | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{run_id}/fields", {
      params: { path: { run_id: runId } },
      signal,
    });
    if (!data) {
      throw new Error("Expected run fields payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchRunColumns(
  runId: string,
  query: RunColumnsQuery | null,
  signal?: AbortSignal,
): Promise<RunColumnResource[] | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{run_id}/columns", {
      params: { path: { run_id: runId }, query: query ?? undefined },
      signal,
    });
    if (!data) {
      throw new Error("Expected run columns payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function buildRunRecord(run: RunResource): RunRecord {
  const inputName = run.input?.filename ?? run.input?.document_id ?? `Run ${run.id}`;
  const outputName = run.output?.filename ?? null;
  const startedAtLabel = formatTimestamp(run.started_at ?? run.created_at);
  const durationLabel = formatDuration(run.duration_seconds ?? null, run.status);
  const configLabel = run.config_version ?? run.configuration_id ?? "—";

  return {
    id: run.id,
    configurationId: run.configuration_id,
    status: run.status,
    inputName,
    outputName,
    configLabel,
    startedAtLabel,
    durationLabel,
    rows: null,
    warnings: null,
    errors: null,
    quality: null,
    ownerLabel: "—",
    triggerLabel: "—",
    engineLabel: run.engine_version ?? "—",
    regionLabel: "—",
    notes: run.failure_message ?? null,
    raw: run,
  };
}
