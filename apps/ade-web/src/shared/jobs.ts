import { client } from "@shared/api/client";
import type { components, paths } from "@schema";

export type JobRecord = components["schemas"]["JobRecord"];
export type JobStatus = JobRecord["status"];

type ListJobsParameters = paths["/api/v1/workspaces/{workspace_id}/jobs"]["get"]["parameters"];
type ListJobsQuery = ListJobsParameters extends { query?: infer Q }
  ? (Q extends undefined ? Record<string, never> : Q)
  : Record<string, never>;

export async function fetchWorkspaceJobs(
  workspaceId: string,
  options: {
    status?: JobStatus | "all" | null;
    inputDocumentId?: string | null;
    limit?: number | null;
    offset?: number | null;
  },
  signal?: AbortSignal,
): Promise<JobRecord[]> {
  const query: ListJobsQuery = {};
  if (options.status && options.status !== "all") query.status = options.status;
  if (options.inputDocumentId) query.input_document_id = options.inputDocumentId;
  if (typeof options.limit === "number") query.limit = options.limit;
  if (typeof options.offset === "number") query.offset = options.offset;

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/jobs", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  return (data ?? []) as JobRecord[];
}

export const workspaceJobsKeys = {
  all: (workspaceId: string) => ["workspace-jobs", workspaceId] as const,
  list: (workspaceId: string, filterKey: unknown) =>
    [...workspaceJobsKeys.all(workspaceId), "list", filterKey] as const,
};
