import { Navigate } from "react-router-dom";

import { useWorkspacesQuery } from "../../../features/workspaces/api/queries";
import { useSession } from "../../../features/auth/context/SessionContext";
import { readPreferredWorkspaceId } from "../../../features/workspaces/lib/workspace";
import { getDefaultWorkspacePath } from "../workspaces/$workspaceId/loader";
import { Button } from "../../../ui/button";
import { PageState } from "../../../ui/PageState";

export default function RootIndexRoute() {
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();

  if (workspacesQuery.isLoading) {
    return <PageState title="Loading workspaces" variant="loading" />;
  }

  if (workspacesQuery.isError) {
    return (
      <PageState
        title="Unable to load workspaces"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => workspacesQuery.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  const workspaces = workspacesQuery.data ?? [];

  if (workspaces.length === 0) {
    return <Navigate to="/workspaces" replace />;
  }

  const preferredIds = [readPreferredWorkspaceId(), session.user.preferred_workspace_id]
    .filter((value): value is string => Boolean(value));

  const preferredWorkspace = preferredIds
    .map((id) => workspaces.find((workspace) => workspace.id === id))
    .find((match) => Boolean(match));

  const targetWorkspace = preferredWorkspace ?? workspaces[0];

  return <Navigate to={getDefaultWorkspacePath(targetWorkspace.id)} replace />;
}
