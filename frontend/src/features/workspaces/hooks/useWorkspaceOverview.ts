import { useQuery } from "@tanstack/react-query";

import { listActiveConfigurations } from "@api/configurations";
import { listDocuments } from "@api/documents";
import { listJobs } from "@api/jobs";
import { getWorkspaceContext } from "@api/workspaces";
import { useApiClient } from "@hooks/useApiClient";

import type { WorkspaceOverview } from "@features/workspaces/overview-types";

const RECENT_LIMIT = 5;

export function useWorkspaceOverview(workspaceId: string | null) {
  const client = useApiClient();

  return useQuery<WorkspaceOverview, Error>({
    queryKey: ["workspace-overview", workspaceId],
    enabled: Boolean(workspaceId),
    queryFn: async () => {
      if (!workspaceId) {
        throw new Error("Workspace ID is required");
      }

      const [workspace, documents, jobs, configurations] = await Promise.all([
        getWorkspaceContext(client, workspaceId),
        listDocuments(client, workspaceId, { limit: RECENT_LIMIT }),
        listJobs(client, workspaceId, { limit: RECENT_LIMIT }),
        listActiveConfigurations(client, workspaceId)
      ]);

      const activeConfiguration = configurations[0] ?? null;

      return {
        workspace: {
          id: workspace.workspaceId,
          name: workspace.name
        },
        recentDocuments: documents.slice(0, RECENT_LIMIT).map((doc) => ({
          id: doc.documentId,
          filename: doc.originalFilename,
          createdAt: doc.createdAt,
          byteSize: doc.byteSize,
          contentType: doc.contentType
        })),
        activeJobs: jobs.slice(0, RECENT_LIMIT).map((job) => ({
          id: job.jobId,
          name: job.documentType,
          status: job.status,
          startedAt: job.createdAt
        })),
        configuration: {
          activeConfiguration: activeConfiguration?.title ?? "No active configuration",
          updatedAt: activeConfiguration?.updatedAt ?? ""
        }
      } satisfies WorkspaceOverview;
    }
  });
}
