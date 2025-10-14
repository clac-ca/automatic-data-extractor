import { Navigate } from "react-router-dom";

import { useSessionQuery } from "../../features/auth/hooks/useSessionQuery";
import { useWorkspacesQuery } from "../../features/workspaces/hooks/useWorkspacesQuery";
import { readPreferredWorkspaceId } from "../../shared/lib/workspace";
import { getDefaultWorkspacePath } from "../workspaces/loader";
import { Button } from "../../ui";
import { PageState } from "../components/PageState";

export function HomeRedirectRoute() {
  const { session } = useSessionQuery();
  const workspacesQuery = useWorkspacesQuery();

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Loading workspaces" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
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
      </div>
    );
  }

  const workspaces = workspacesQuery.data ?? [];

  if (workspaces.length === 0) {
    return <Navigate to="/workspaces" replace />;
  }

  const preferredIds = [readPreferredWorkspaceId(), session?.user.preferred_workspace_id]
    .filter((value): value is string => Boolean(value));

  const preferredWorkspace = preferredIds
    .map((id) => workspaces.find((workspace) => workspace.id === id))
    .find((match) => Boolean(match));

  const targetWorkspace = preferredWorkspace ?? workspaces[0];

  return <Navigate to={getDefaultWorkspacePath(targetWorkspace.id)} replace />;
}
