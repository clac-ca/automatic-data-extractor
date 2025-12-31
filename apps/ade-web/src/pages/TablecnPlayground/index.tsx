import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { PageState } from "@components/layouts/page-state";
import { Button } from "@components/ui/button";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { useNavigate } from "@app/navigation/history";
import { fetchWorkspaceDocuments } from "@pages/Workspace/sections/Documents/data";
import { readPreferredWorkspaceId } from "@utils/workspaces";
import { TablecnDocumentsTable } from "./components/TablecnDocumentsTable";
import { TablecnPlaygroundLayout } from "./components/TablecnPlaygroundLayout";
import { useDocumentsPagination } from "./hooks/useDocumentsPagination";

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

  return <TablecnDocumentsContainer workspaceId={workspace.id} />;
}

function TablecnDocumentsContainer({ workspaceId }: { workspaceId: string }) {
  const { page, perPage } = useDocumentsPagination();
  const documentsQuery = useQuery({
    queryKey: ["tablecn-documents", workspaceId, page, perPage],
    queryFn: ({ signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        { sort: null, page, pageSize: perPage },
        signal,
      ),
    enabled: Boolean(workspaceId),
  });

  if (documentsQuery.isLoading) {
    return <PageState title="Loading documents" variant="loading" />;
  }

  if (documentsQuery.isError) {
    return (
      <PageState
        title="Unable to load documents"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => documentsQuery.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  const pageCount = documentsQuery.data
    ? documentsQuery.data.has_next
      ? documentsQuery.data.page + 1
      : documentsQuery.data.page
    : 1;

  return (
    <TablecnPlaygroundLayout>
      <TablecnDocumentsTable
        data={documentsQuery.data?.items ?? []}
        pageCount={pageCount}
      />
    </TablecnPlaygroundLayout>
  );
}
