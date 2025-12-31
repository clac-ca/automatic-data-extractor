import { useMemo } from "react";

import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { PageState } from "@components/layouts/page-state";
import { Button } from "@components/ui/button";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { useNavigate } from "@navigation/history";
import { DocumentsWorkbench } from "@pages/Documents";
import { WorkspaceProvider } from "@pages/Workspace/context/WorkspaceContext";
import { readPreferredWorkspaceId } from "@utils/workspaces";

export default function TablecnPlaygroundScreen() {
  return (
    <RequireSession>
      <TablecnDocumentsPlayground />
    </RequireSession>
  );
}

function TablecnDocumentsPlayground() {
  const session = useSession();
  const navigate = useNavigate();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data?.items],
  );

  const preferredIds = useMemo(
    () =>
      [readPreferredWorkspaceId(), session.user.preferred_workspace_id].filter(
        (value): value is string => Boolean(value),
      ),
    [session.user.preferred_workspace_id],
  );

  const preferredWorkspace = useMemo(
    () =>
      preferredIds
        .map((id) => workspaces.find((workspace) => workspace.id === id))
        .find((match) => Boolean(match)),
    [preferredIds, workspaces],
  );

  const workspace = preferredWorkspace ?? workspaces[0] ?? null;

  if (workspacesQuery.isLoading) {
    return <PageState title="Loading documents" variant="loading" />;
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

  if (!workspace) {
    return (
      <PageState
        title="No workspaces yet"
        description="Create a workspace to view documents."
        variant="empty"
        action={
          <Button variant="secondary" onClick={() => navigate("/workspaces")}>
            Go to workspaces
          </Button>
        }
      />
    );
  }

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <div className="flex min-h-screen flex-col">
        <DocumentsWorkbench />
      </div>
    </WorkspaceProvider>
  );
}
