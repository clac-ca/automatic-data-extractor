import { client } from "@shared/api/client";
import type { components, paths, RunResource } from "@schema";

import type { RunRecord } from "./types";
import { formatDuration, formatTimestamp } from "./utils";

type RunsQuery = paths["/api/v1/workspaces/{workspace_id}/runs"]["get"]["parameters"]["query"];
type RunPage = components["schemas"]["RunPage"];

export const RUNS_PAGE_SIZE = 50;

export const runsKeys = {
  root: () => ["runs"] as const,
  workspace: (workspaceId: string) => [...runsKeys.root(), workspaceId] as const,
  list: (workspaceId: string, query: RunsQuery) => [...runsKeys.workspace(workspaceId), "list", query] as const,
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

export function buildRunRecord(run: RunResource): RunRecord {
  const inputName = run.input?.filename ?? run.input?.document_id ?? `Run ${run.id}`;
  const outputName = run.output?.filename ?? null;
  const startedAtLabel = formatTimestamp(run.started_at ?? run.created_at);
  const durationLabel = formatDuration(run.duration_seconds ?? null, run.status);
  const configLabel = run.config_version ?? run.configuration_id ?? "—";

  return {
    id: run.id,
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
