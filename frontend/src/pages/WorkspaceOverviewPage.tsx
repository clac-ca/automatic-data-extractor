import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

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

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {workspace ? workspace.name : "Workspace overview"}
          </h1>
          <p className="page-intro">
            {workspace
              ? `You’re viewing ${workspace.slug} as a ${workspace.role.toLowerCase()}.`
              : isLoading
                ? "Loading workspace details…"
                : "Select a workspace from the directory."}
          </p>
        </div>
      </div>
      {workspace ? (
        <>
          <section className="card" style={{ gridColumn: "1 / -1" }}>
            <h2 className="card-title">Document activity</h2>
            <p className="page-subtitle">
              Recent uploads and job runs will appear here once ingestion is complete.
            </p>
            <Link
              to={`/workspaces/${workspace.workspace_id}/documents`}
              className="button-secondary"
            >
              View documents
            </Link>
          </section>
          <section className="card" style={{ gridColumn: "1 / -1" }}>
            <h2 className="card-title">Next steps</h2>
            <ul>
              <li>Upload a sample document to validate configuration defaults.</li>
              <li>Review the jobs tab to monitor processing status.</li>
              <li>Align configuration payloads with backend schema expectations.</li>
            </ul>
          </section>
        </>
      ) : (
        <section className="card" style={{ gridColumn: "1 / -1" }}>
          {isLoading ? (
            <p className="page-subtitle">Loading workspace…</p>
          ) : (
            <p className="page-subtitle">
              Workspace not found. Return to the <Link to="/workspaces">workspace directory</Link>.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
