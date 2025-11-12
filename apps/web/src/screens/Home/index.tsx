import { useEffect } from "react";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery } from "@screens/Workspace/api/workspaces-api";
import { readPreferredWorkspaceId } from "@screens/Workspace/state/workspace-preferences";
import { getDefaultWorkspacePath } from "@screens/Workspace";
import { Button } from "@ui/button";
import { PageState } from "@ui/PageState";
import { useLocation, useNavigate } from "@app/nav/history";

export default function RootIndexRoute() {
  return (
    <RequireSession>
      <RootIndexContent />
    </RequireSession>
  );
}

function RootIndexContent() {
  const location = useLocation();
  const navigate = useNavigate();
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

  const preferredIds = [readPreferredWorkspaceId(), session.user.preferred_workspace_id]
    .filter((value): value is string => Boolean(value));

  const preferredWorkspace = preferredIds
    .map((id) => workspaces.find((workspace) => workspace.id === id))
    .find((match) => Boolean(match));

  const targetWorkspace = preferredWorkspace ?? workspaces[0] ?? null;

  useEffect(() => {
    if (workspacesQuery.isLoading || workspacesQuery.isError) {
      return;
    }

    if (!targetWorkspace) {
      if (location.pathname !== "/workspaces") {
        navigate("/workspaces", { replace: true });
      }
      return;
    }

    const targetPath = getDefaultWorkspacePath(targetWorkspace.id);
    if (location.pathname + location.search !== targetPath) {
      navigate(targetPath, { replace: true });
    }
  }, [
    location.pathname,
    location.search,
    navigate,
    targetWorkspace,
    workspacesQuery.isError,
    workspacesQuery.isLoading,
  ]);

  return null;
}
