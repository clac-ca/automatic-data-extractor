import { Link } from "react-router-dom";

import { Card } from "@components/layout/Card";
import { EmptyState } from "@components/layout/EmptyState";
import { PageHeader } from "@components/layout/PageHeader";
import { Button } from "@components/primitives/Button";
import { useWorkspace } from "@hooks/useWorkspace";

import { useWorkspacesQuery } from "@features/workspaces/hooks/useWorkspacesQuery";

import "@styles/page-grid.css";
import "@styles/workspaces-page.css";

export function WorkspacesPage(): JSX.Element {
  const { data, isLoading } = useWorkspacesQuery();
  const { setWorkspace } = useWorkspace();

  const workspaces = data?.workspaces ?? [];

  return (
    <div className="page-grid">
      <PageHeader
        title="Workspaces"
        description="Browse workspaces, review access, and jump into active projects."
        actions={
          <Button variant="secondary" size="sm" disabled>
            New workspace
          </Button>
        }
      />
      {isLoading ? (
        <div className="workspace-grid">
          {[0, 1, 2].map((item) => (
            <div key={item} className="workspace-card workspace-card--loading" />
          ))}
        </div>
      ) : null}
      {!isLoading && workspaces.length === 0 ? (
        <EmptyState
          title="No workspaces yet"
          description="Create a workspace to start uploading documents and launching extraction jobs."
          action={
            <Button variant="primary" size="md" disabled>
              Create workspace
            </Button>
          }
        />
      ) : null}
      {!isLoading && workspaces.length > 0 ? (
        <div className="workspace-grid">
          {workspaces.map((workspace) => (
            <Card key={workspace.workspaceId}>
              <div className="workspace-card">
                <div>
                  <h2 className="workspace-card__title">{workspace.name}</h2>
                  <p className="workspace-card__meta">
                    {workspace.slug} · Role: {workspace.role}
                  </p>
                  {workspace.isDefault ? (
                    <span className="workspace-card__badge">Default</span>
                  ) : null}
                </div>
                <Link
                  className="workspace-card__link"
                  to={`/workspaces/${workspace.workspaceId}/overview`}
                  onClick={() => setWorkspace(workspace.workspaceId)}
                >
                  Open workspace
                </Link>
              </div>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  );
}
