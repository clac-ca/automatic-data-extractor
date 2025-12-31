import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";

import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { PageState } from "@components/layouts/page-state";
import { DataTable } from "@components/tablecn/data-table/data-table";
import { DataTableColumnHeader } from "@components/tablecn/data-table/data-table-column-header";
import { useDataTable } from "@components/tablecn/hooks/use-data-table";
import { Badge } from "@components/tablecn/ui/badge";
import { Button } from "@components/ui/button";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { useNavigate } from "@app/navigation/history";
import { useSearchParams } from "@app/navigation/urlState";
import { fetchWorkspaceDocuments } from "@pages/Documents/data";
import type { DocumentListRow } from "@pages/Documents/types";
import { fileTypeLabel } from "@pages/Documents/utils";
import { readPreferredWorkspaceId } from "@utils/workspaces";

const DEFAULT_PAGE_SIZE = 50;

function parseNumberParam(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

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

  return <TablecnDocumentsTable workspaceId={workspace.id} />;
}

function TablecnDocumentsTable({ workspaceId }: { workspaceId: string }) {
  const [searchParams] = useSearchParams();
  const page = useMemo(
    () => parseNumberParam(searchParams.get("page"), 1),
    [searchParams],
  );
  const perPage = useMemo(
    () => parseNumberParam(searchParams.get("perPage"), DEFAULT_PAGE_SIZE),
    [searchParams],
  );

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

  const columns = useMemo<ColumnDef<DocumentListRow>[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Document" />
        ),
        cell: ({ row }) => (
          <div className="min-w-[220px] font-medium">
            {row.getValue<string>("name")}
          </div>
        ),
        enableSorting: false,
        enableHiding: false,
      },
      {
        id: "status",
        accessorKey: "status",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Status" />
        ),
        cell: ({ row }) => (
          <Badge variant="outline" className="capitalize">
            {row.getValue<string>("status")}
          </Badge>
        ),
        enableSorting: false,
        enableHiding: false,
      },
      {
        id: "file_type",
        accessorKey: "file_type",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Type" />
        ),
        cell: ({ row }) =>
          fileTypeLabel(row.getValue<DocumentListRow["file_type"]>("file_type")),
        enableSorting: false,
        enableHiding: false,
      },
      {
        id: "size_label",
        accessorKey: "size_label",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Size" />
        ),
        cell: ({ row }) => row.getValue<string>("size_label") || "-",
        enableSorting: false,
        enableHiding: false,
      },
      {
        id: "created_at",
        accessorKey: "created_at",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Created" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("created_at")),
        enableSorting: false,
        enableHiding: false,
      },
    ],
    [],
  );

  const pageCount = documentsQuery.data
    ? documentsQuery.data.has_next
      ? documentsQuery.data.page + 1
      : documentsQuery.data.page
    : 1;

  const { table } = useDataTable({
    data: documentsQuery.data?.items ?? [],
    columns,
    pageCount,
    initialState: {
      pagination: { pageSize: DEFAULT_PAGE_SIZE },
    },
    getRowId: (row) => row.id,
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

  return (
    <div className="flex min-h-screen flex-col gap-4 p-6">
      <div>
        <h1 className="text-lg font-semibold">Tablecn playground</h1>
        <p className="text-muted-foreground text-sm">
          Minimal documents table (read-only).
        </p>
      </div>
      <DataTable table={table} />
    </div>
  );
}
