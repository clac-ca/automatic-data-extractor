import type { RunColumnsQuery } from "@api/runs/api";

export const runsKeys = {
  root: () => ["runs"] as const,
  workspace: (workspaceId: string) => [...runsKeys.root(), workspaceId] as const,
  list: (workspaceId: string, params: Record<string, unknown>) =>
    [...runsKeys.workspace(workspaceId), "list", params] as const,
  run: (runId: string) => [...runsKeys.root(), "run", runId] as const,
  metrics: (runId: string) => [...runsKeys.run(runId), "metrics"] as const,
  fields: (runId: string) => [...runsKeys.run(runId), "fields"] as const,
  columns: (runId: string, query: RunColumnsQuery | null) => [...runsKeys.run(runId), "columns", query ?? {}] as const,
};
