import { get, post } from "../../shared/api/client";
import type { JobRecord, JobStatus, JobSubmissionPayload } from "../../shared/types/jobs";

function buildJobsPath(workspaceId: string, suffix: string = "") {
  const trimmed = suffix.startsWith("/") ? suffix : `/${suffix}`;
  return `/workspaces/${workspaceId}/jobs${trimmed === "/" ? "" : trimmed}`;
}

export interface ListJobsOptions {
  readonly status?: JobStatus | "all" | null;
  readonly inputDocumentId?: string | null;
  readonly limit?: number;
  readonly offset?: number;
  readonly signal?: AbortSignal;
}

export async function listJobs(workspaceId: string, options: ListJobsOptions = {}) {
  const params = new URLSearchParams();
  if (options.status && options.status !== "all") {
    params.set("status", options.status);
  }
  if (options.inputDocumentId) {
    params.set("input_document_id", options.inputDocumentId);
  }
  if (typeof options.limit === "number") {
    params.set("limit", String(options.limit));
  }
  if (typeof options.offset === "number" && options.offset > 0) {
    params.set("offset", String(options.offset));
  }

  const search = params.toString();
  const path = search.length > 0 ? `${buildJobsPath(workspaceId)}?${search}` : buildJobsPath(workspaceId);
  return get<JobRecord[]>(path, { signal: options.signal });
}

export function submitJob(workspaceId: string, payload: JobSubmissionPayload) {
  return post<JobRecord>(buildJobsPath(workspaceId), payload);
}

export function getJob(workspaceId: string, jobId: string, signal?: AbortSignal) {
  return get<JobRecord>(buildJobsPath(workspaceId, `/${jobId}`), { signal });
}
