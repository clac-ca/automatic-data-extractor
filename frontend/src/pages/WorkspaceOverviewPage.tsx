import { Link, useParams } from "react-router-dom";
import { useEffect } from "react";

import { useWorkspaceContextQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";

export function WorkspaceOverviewPage() {
  const { workspaceId } = useParams();
  const { setSelectedWorkspaceId } = useWorkspaceSelection();
  const { data, isLoading } = useWorkspaceContextQuery(workspaceId ?? null);
  const workspace = data?.workspace;

  const resolvedWorkspaceId = workspace?.workspace_id ?? null;

  useEffect(() => {
    if (resolvedWorkspaceId) {
      setSelectedWorkspaceId(resolvedWorkspaceId);
    }
  }, [resolvedWorkspaceId, setSelectedWorkspaceId]);

  if (!workspaceId) {
    return (
      <div className="page">
        <h1 className="page-title">Workspace not specified</h1>
        <p>Please choose a workspace to continue.</p>
        <Link to="/workspaces">Return to workspaces</Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page">
        <h1 className="page-title">Loading workspace…</h1>
        <p className="muted">Fetching workspace details.</p>
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="page">
        <h1 className="page-title">Workspace not found</h1>
        <p>Check the URL and try again.</p>
        <Link to="/workspaces">Return to workspaces</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <h1 className="page-title">{workspace.name}</h1>
      <p className="page-intro">
        You&apos;re viewing the {workspace.slug} workspace as a {" "}
        {workspace.role.toLowerCase()}.
      </p>

      <section className="section">
        <header className="section-header">
          <h2>Document types</h2>
          <Link to={`/workspaces/${workspace.workspace_id}/documents`}>
            Manage documents
          </Link>
        </header>
        <div className="placeholder-card">
          <p>
            Configure document types under <strong>Configurations</strong> to see
            them listed here. Active configurations will power uploads and
            extraction jobs for this workspace.
          </p>
        </div>
      </section>
    </div>
  );
}
