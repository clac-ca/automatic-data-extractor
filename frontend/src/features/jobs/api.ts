import { client } from "@shared/api/client";
import type { components, paths } from "@api-types";

export interface ListJobsOptions {
  readonly status?: JobStatus | "all" | null;
  readonly inputDocumentId?: string | null;
  readonly limit?: number;
  readonly offset?: number;
  readonly signal?: AbortSignal;
}

export async function listJobs(workspaceId: string, options: ListJobsOptions = {}) {
  const query: ListJobsQuery = {};

  if (options.status && options.status !== "all") {
    query.status = options.status;
  }
  if (options.inputDocumentId) {
    query.input_document_id = options.inputDocumentId;
  }
  if (typeof options.limit === "number") {
    query.limit = options.limit;
  }
  if (typeof options.offset === "number") {
    query.offset = options.offset;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/jobs", {
    params: {
      path: { workspace_id: workspaceId },
      query,
    },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected jobs response.");
  }

  return data.map(normaliseJobRecord);
}

export function submitJob(workspaceId: string, payload: JobSubmissionPayload) {
  return client
    .POST("/api/v1/workspaces/{workspace_id}/jobs", {
      params: { path: { workspace_id: workspaceId } },
      body: payload,
    })
    .then((result) => {
      if (!result.data) {
        throw new Error("Expected submitted job response.");
      }
      return normaliseJobRecord(result.data);
    });
}

export function getJob(workspaceId: string, jobId: string, signal?: AbortSignal) {
  return client
    .GET("/api/v1/workspaces/{workspace_id}/jobs/{job_id}", {
      params: {
        path: {
          workspace_id: workspaceId,
          job_id: jobId,
        },
      },
      signal,
    })
    .then((result) => {
      if (!result.data) {
        throw new Error("Expected job response.");
      }
      return normaliseJobRecord(result.data);
    });
}

function normaliseJobRecord(record: components["schemas"]["JobRecord"]): JobRecord {
  return {
    ...record,
    status: record.status as JobStatus,
  };
}

type ListJobsQuery =
  paths["/api/v1/workspaces/{workspace_id}/jobs"]["get"]["parameters"]["query"] extends undefined
    ? Record<string, never>
    : paths["/api/v1/workspaces/{workspace_id}/jobs"]["get"]["parameters"]["query"];

export type JobSubmissionPayload = components["schemas"]["JobSubmissionRequest"];
export type JobRecord = Readonly<
  Omit<components["schemas"]["JobRecord"], "status"> & {
    status: JobStatus;
  }
>;

export type JobStatus = "pending" | "running" | "succeeded" | "failed";
