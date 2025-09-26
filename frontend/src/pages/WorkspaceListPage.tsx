import { Link } from "react-router-dom";

import { useWorkspacesQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";

export function WorkspaceListPage() {
  const { data, isLoading } = useWorkspacesQuery();
  const { setSelectedWorkspaceId } = useWorkspaceSelection();

  if (isLoading) {
    return (
      <div className="page">
        <h1 className="page-title">Workspaces</h1>
        <p className="muted">Loading workspaces…</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="page">
        <h1 className="page-title">Workspaces</h1>
        <p className="page-intro">
          You don&apos;t have access to any workspaces yet. Ask an administrator to
          share one with you.
        </p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1 className="page-title">Workspaces</h1>
      <p className="page-intro">
        Choose a workspace to manage its document types and review the latest
        extraction activity.
      </p>
      <div className="card-grid">
        {data.map((workspace) => (
          <article key={workspace.workspace_id} className="card">
            <h2>{workspace.name}</h2>
            <p className="muted">Slug: {workspace.slug}</p>
            <p className="badge">
              Role: {workspace.role.replace(/_/g, " ").toLowerCase()}
            </p>
            <p className="muted">
              Permissions: {workspace.permissions.join(", ") || "None"}
            </p>
            {workspace.is_default ? (
              <p className="badge badge-info">Default workspace</p>
            ) : null}
            <Link
              to={`/workspaces/${workspace.workspace_id}`}
              className="button-link"
              onClick={() => setSelectedWorkspaceId(workspace.workspace_id)}
            >
              Open workspace
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
