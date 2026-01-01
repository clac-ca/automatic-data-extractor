import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@api/client";
import { ApiError } from "@api/errors";
import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { PageState } from "@components/layouts/page-state";
import { Button } from "@components/ui/button";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { useNavigate } from "@app/navigation/history";
import { readPreferredWorkspaceId } from "@lib/workspacePreferences";
import { TablecnDocumentsTable } from "./components/TablecnDocumentsTable";
import { TablecnPlaygroundLayout } from "./components/TablecnPlaygroundLayout";
import { useDocumentsListParams } from "./hooks/useDocumentsListParams";
import type { DocumentListResponse, DocumentsListParams } from "./types";
import { buildDocumentsListQuery } from "./utils";

export default function TablecnPlaygroundScreen() {
  return (
    <RequireSession>
      <TablecnDocumentsPlayground />
    </RequireSession>
  );
}

async function fetchTablecnDocuments(
  workspaceId: string,
  params: DocumentsListParams,
  signal?: AbortSignal,
) {
  const query = buildDocumentsListQuery(params);
  const url = `/api/v1/workspaces/${workspaceId}/documents?${query.toString()}`;
  const response = await apiFetch(url, { signal });
  if (!response.ok) {
    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, problem);
  }
  return (await response.json()) as DocumentListResponse;
}

async function tryParseProblem(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return (await response.clone().json()) as {
      title?: string;
      detail?: string;
      status?: number;
    };
  } catch {
    return undefined;
  }
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
  const { page, perPage, sort, filters, joinOperator, q } =
    useDocumentsListParams();
  const documentsQuery = useQuery({
    queryKey: [
      "tablecn-documents",
      workspaceId,
      page,
      perPage,
      sort,
      filters,
      joinOperator,
      q,
    ],
    queryFn: ({ signal }) =>
      fetchTablecnDocuments(
        workspaceId,
        { page, perPage, sort, filters, joinOperator, q },
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

  const pageCount = documentsQuery.data?.pageCount ?? 1;

  return (
    <TablecnPlaygroundLayout>
      <TablecnDocumentsTable
        data={documentsQuery.data?.items ?? []}
        pageCount={pageCount}
      />
    </TablecnPlaygroundLayout>
  );
}
