import { Navigate } from "react-router-dom";

import { Card } from "@components/layout/Card";
import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";
import { formatBytes, formatDateTime } from "@utils/format";

import { useWorkspaceOverview } from "@features/workspaces/hooks/useWorkspaceOverview";

import "@styles/page-grid.css";

export function WorkspaceOverviewPage(): JSX.Element {
  const { workspaceId } = useWorkspace();
  const { data, isLoading, error } = useWorkspaceOverview(workspaceId ?? null);

  if (!workspaceId) {
    return (
      <EmptyState
        title="Select a workspace"
        description="Choose a workspace from the top bar to view its overview."
      />
    );
  }

  if (error) {
    return (
      <EmptyState
        title="Unable to load workspace"
        description={error.message}
        action={
          <Button variant="primary" size="sm" onClick={() => window.location.reload()}>
            Retry
          </Button>
        }
      />
    );
  }

  if (!isLoading && !data) {
    return <Navigate to="/workspaces" replace />;
  }

  return (
    <div className="page-grid">
      <PageHeader
        title={data?.workspace.name ?? "Workspace overview"}
        description="Recent documents, active jobs, and configuration status."
      />
      <div className="overview-grid">
        <Card title="Documents" subtitle="Recent uploads">
          {isLoading ? (
            <p>Loading documents...</p>
          ) : (
            <ul className="overview-list">
              {data?.recentDocuments.length ? (
                data.recentDocuments.map((doc) => (
                  <li key={doc.id}>
                    <div className="overview-list__title">{doc.filename}</div>
                    <div className="overview-list__meta">
                      {formatDateTime(doc.createdAt)} · {formatBytes(doc.byteSize)}
                    </div>
                  </li>
                ))
              ) : (
                <li>No recent documents</li>
              )}
            </ul>
          )}
        </Card>
        <Card title="Active jobs" subtitle="Jobs in progress or recently finished">
          {isLoading ? (
            <p>Loading jobs...</p>
          ) : (
            <ul className="overview-list">
              {data?.activeJobs.length ? (
                data.activeJobs.map((job) => (
                  <li key={job.id}>
                    <div className="overview-list__title">{job.name}</div>
                    <div className="overview-list__meta">
                      Status: {job.status} · {formatDateTime(job.startedAt)}
                    </div>
                  </li>
                ))
              ) : (
                <li>No active jobs</li>
              )}
            </ul>
          )}
        </Card>
        <Card title="Configuration" subtitle="Current configuration state">
          {isLoading ? (
            <p>Loading configuration...</p>
          ) : (
            <div className="configuration-summary">
              <div className="configuration-summary__item">
                <span className="configuration-summary__label">Active configuration</span>
                <span className="configuration-summary__value">
                  {data?.configuration.activeConfiguration ?? "Not set"}
                </span>
              </div>
              <div className="configuration-summary__item">
                <span className="configuration-summary__label">Last updated</span>
                <span className="configuration-summary__value">
                  {data?.configuration.updatedAt
                    ? formatDateTime(data.configuration.updatedAt)
                    : "Unknown"}
                </span>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
