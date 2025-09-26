import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { useWorkspaceContextQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";

export function WorkspaceResultsPage() {
  const params = useParams();
  const routeWorkspaceId = params.workspaceId ?? null;
  const { setSelectedWorkspaceId } = useWorkspaceSelection();
  const { data: workspaceContext } = useWorkspaceContextQuery(routeWorkspaceId);
  const workspace = workspaceContext?.workspace;
  const workspaceId = workspace?.workspace_id ?? null;

  useEffect(() => {
    if (workspaceId) {
      setSelectedWorkspaceId(workspaceId);
    }
  }, [workspaceId, setSelectedWorkspaceId]);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Results</h1>
          <p className="page-subtitle">
            {workspace ? workspace.name : "Select a workspace to review results."}
          </p>
        </div>
      </div>
      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <p className="page-subtitle">
          The results explorer will appear here once job processing is connected.
        </p>
      </section>
    </div>
  );
}
