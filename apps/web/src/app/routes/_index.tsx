import { Navigate } from "react-router";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery } from "./workspaces/workspaces-api";
import { readPreferredWorkspaceId } from "./workspaces/workspace-preferences";
import { getDefaultWorkspacePath } from "./workspaces.$workspaceId/route";
import { Button } from "@ui/button";
import { PageState } from "@ui/PageState";

export default function RootIndexRoute() {
  return (
    <RequireSession>
      <RootIndexContent />
    </RequireSession>
  );
}

function RootIndexContent() {
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

  const workspaces = workspacesQuery.data?.items ?? [];

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
