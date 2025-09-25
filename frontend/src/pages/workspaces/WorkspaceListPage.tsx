import { Link } from "react-router-dom";

import { Button } from "@components/Button";
import { Card } from "@components/Card";
import { Page } from "@components/Page";
import type { WorkspaceProfile } from "@api/schemas/workspaces";

export function WorkspaceListPage({
  workspaces,
  isLoading,
}: {
  workspaces?: WorkspaceProfile[];
  isLoading: boolean;
}) {
  return (
    <Page
      title="Workspaces"
      description="Select a workspace to explore documents, jobs, and configurations."
      actions={<Button variant="secondary">TODO: Create workspace</Button>}
    >
      {isLoading ? (
        <div className="loading-state">
          <span className="loading-state__spinner" aria-hidden="true" />
          <span>Loading workspaces</span>
        </div>
      ) : (
        <div className="workspace-grid">
          {workspaces?.map((workspace) => (
            <WorkspaceCard key={workspace.workspace_id} workspace={workspace} />
          ))}
        </div>
      )}
    </Page>
  );
}

function WorkspaceCard({ workspace }: { workspace: WorkspaceProfile }) {
  return (
    <Card className="workspace-card">
      <h2>{workspace.name}</h2>
      <p>{workspace.slug}</p>
      <div className="workspace-card__meta">
        <span className="workspace-card__role">Role: {workspace.role}</span>
        <Link className="workspace-card__link" to={`/workspaces/${workspace.workspace_id}`}>
          Enter workspace →
        </Link>
      </div>
    </Card>
  );
}
