import { Link } from "react-router-dom";

import { useWorkspacesQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";

export function WorkspaceListPage() {
  const { data, isLoading } = useWorkspacesQuery();
  const { setSelectedWorkspaceId } = useWorkspaceSelection();

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Workspaces</h1>
          <p className="page-intro">
            Choose a workspace to manage uploads, jobs, and configuration states.
          </p>
        </div>
      </div>
      {isLoading ? (
        <section className="card" style={{ gridColumn: "1 / -1" }}>
          <p className="page-subtitle">Loading workspaces…</p>
        </section>
      ) : !data || data.length === 0 ? (
        <section className="card" style={{ gridColumn: "1 / -1" }}>
          <p className="page-subtitle">
            You don&apos;t have access to any workspaces yet. Ask an administrator to
            share one with you.
          </p>
        </section>
      ) : (
        <div className="workspace-grid">
          {data.map((workspace) => (
            <article key={workspace.workspace_id} className="card">
              <h2 className="card-title">{workspace.name}</h2>
              <p className="muted">Slug: {workspace.slug}</p>
              <p className="badge neutral">
                Role: {workspace.role.replace(/_/g, " ").toLowerCase()}
              </p>
              <p className="page-subtitle">
                Permissions: {workspace.permissions.join(", ") || "None"}
              </p>
              {workspace.is_default ? (
                <p className="badge success">Default workspace</p>
              ) : null}
              <div className="card-footer">
                <Link
                  to={`/workspaces/${workspace.workspace_id}/overview`}
                  className="button-primary"
                  onClick={() => setSelectedWorkspaceId(workspace.workspace_id)}
                >
                  Open workspace
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
