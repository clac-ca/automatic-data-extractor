import { useEffect } from "react";

import { useSession } from "@/providers/auth/SessionContext";
import { useWorkspacesQuery } from "@/hooks/workspaces";
import { getDefaultWorkspacePath } from "@/navigation/workspacePaths";
import { readPreferredWorkspaceId } from "@/lib/workspacePreferences";
import type { WorkspaceProfile } from "@/types/workspaces";
import { Button } from "@/components/ui/button";
import { PageState } from "@/components/layout";
import { useLocation, useNavigate } from "react-router-dom";

export default function HomeScreen() {
  return <RootIndexContent />;
}

function RootIndexContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces: WorkspaceProfile[] = workspacesQuery.data?.items ?? [];

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

  return null;
}
