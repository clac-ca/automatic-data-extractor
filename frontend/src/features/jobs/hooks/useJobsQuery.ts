import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { jobsKeys } from "../api/keys";
import { getJob, listJobs, submitJob, type ListJobsOptions } from "../api";
import type { JobRecord, JobSubmissionPayload } from "@types/jobs";

export function useDocumentJobsQuery(
  workspaceId: string,
  documentId: string,
  { enabled = true, limit = 5 }: { enabled?: boolean; limit?: number } = {},
) {
  return useQuery<JobRecord[]>({
    queryKey: jobsKeys.document(workspaceId, documentId, limit),
    queryFn: ({ signal }) =>
      listJobs(workspaceId, {
        inputDocumentId: documentId,
        limit,
        signal,
      }),
    enabled: enabled && workspaceId.length > 0 && documentId.length > 0,
    staleTime: 10_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function useJobsQuery(workspaceId: string, options: ListJobsOptions = {}) {
  const { status = null, inputDocumentId = null, limit = null, offset = null } = options;
  return useQuery<JobRecord[]>({
    queryKey: jobsKeys.list(workspaceId, status, inputDocumentId, limit, offset),
    queryFn: ({ signal }) =>
      listJobs(workspaceId, {
        ...options,
        signal,
      }),
    enabled: workspaceId.length > 0,
    staleTime: 10_000,
  });
}

export function useJobDetailQuery(workspaceId: string, jobId: string, { enabled = true } = {}) {
  return useQuery<JobRecord>({
    queryKey: jobsKeys.detail(workspaceId, jobId),
    queryFn: ({ signal }) => getJob(workspaceId, jobId, signal),
    enabled: enabled && workspaceId.length > 0 && jobId.length > 0,
    staleTime: 10_000,
  });
}

export function useSubmitJobMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: JobSubmissionPayload) => submitJob(workspaceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: jobsKeys.root(workspaceId) });
    },
  });
}
