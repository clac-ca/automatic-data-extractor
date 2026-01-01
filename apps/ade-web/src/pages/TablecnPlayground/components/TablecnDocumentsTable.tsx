import { useCallback, useMemo, useState, type MouseEvent } from "react";
import type { ColumnDef, Row } from "@tanstack/react-table";

import { DataTable } from "@components/tablecn/data-table/data-table";
import { DataTableAdvancedToolbar } from "@components/tablecn/data-table/data-table-advanced-toolbar";
import { DataTableColumnHeader } from "@components/tablecn/data-table/data-table-column-header";
import { DataTableFilterList } from "@components/tablecn/data-table/data-table-filter-list";
import { DataTableSortList } from "@components/tablecn/data-table/data-table-sort-list";
import { useDataTable } from "@components/tablecn/hooks/use-data-table";
import { Badge } from "@components/tablecn/ui/badge";
import type { DocumentStatus, FileType } from "@pages/Workspace/sections/Documents/types";
import { MappingBadge } from "@pages/Workspace/sections/Documents/components/MappingBadge";
import { fileTypeLabel, formatBytes, shortId } from "@pages/Workspace/sections/Documents/utils";
import { TablecnDocumentPreviewGrid } from "./TablecnDocumentPreviewGrid";
import type { DocumentListRow } from "../types";
import { DEFAULT_PAGE_SIZE, formatTimestamp } from "../utils";

interface TablecnDocumentsTableProps {
  data: DocumentListRow[];
  pageCount: number;
}

const PREVIEWABLE_FILE_TYPES = new Set<FileType>(["xlsx", "csv"]);

export function TablecnDocumentsTable({
  data,
  pageCount,
}: TablecnDocumentsTableProps) {
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  const statusOptions = useMemo(
    () =>
      (["queued", "processing", "ready", "failed", "archived"] as DocumentStatus[])
        .map((value) => ({
          value,
          label: value === "ready" ? "Processed" : value[0]?.toUpperCase() + value.slice(1),
        })),
    [],
  );

  const fileTypeOptions = useMemo(
    () =>
      (["xlsx", "xls", "csv", "pdf", "unknown"] as FileType[]).map((value) => ({
        value,
        label: fileTypeLabel(value),
      })),
    [],
  );

  const columns = useMemo<ColumnDef<DocumentListRow>[]>(
    () => [
      {
        id: "id",
        accessorKey: "id",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="ID" />
        ),
        cell: ({ row }) => (
          <span
            className="font-mono text-xs text-muted-foreground"
            title={row.getValue<string>("id")}
          >
            {shortId(row.getValue<string>("id"))}
          </span>
        ),
        enableHiding: true,
      },
      {
        id: "workspaceId",
        accessorKey: "workspaceId",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Workspace" />
        ),
        cell: ({ row }) => (
          <span
            className="font-mono text-xs text-muted-foreground"
            title={row.getValue<string>("workspaceId")}
          >
            {shortId(row.getValue<string>("workspaceId"))}
          </span>
        ),
        enableSorting: false,
        enableHiding: true,
      },
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
        meta: {
          label: "Document",
          placeholder: "Search documents...",
          variant: "text",
        },
        enableColumnFilter: true,
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
        meta: {
          label: "Status",
          variant: "multiSelect",
          options: statusOptions,
        },
        enableColumnFilter: true,
        enableHiding: false,
      },
      {
        id: "stage",
        accessorKey: "stage",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Stage" />
        ),
        cell: ({ row }) => row.getValue<string | null>("stage") ?? "-",
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "fileType",
        accessorKey: "fileType",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Type" />
        ),
        cell: ({ row }) =>
          fileTypeLabel(row.getValue<FileType>("fileType")),
        meta: {
          label: "Type",
          variant: "multiSelect",
          options: fileTypeOptions,
        },
        enableColumnFilter: true,
        enableSorting: false,
      },
      {
        id: "uploader",
        accessorKey: "uploader",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Uploader" />
        ),
        cell: ({ row }) => renderUserSummary(row.original.uploader),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "uploaderId",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Uploader ID" />
        ),
        cell: ({ row }) => renderUserId(row.original.uploader?.id ?? null),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "assignee",
        accessorKey: "assignee",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Assignee" />
        ),
        cell: ({ row }) => renderUserSummary(row.original.assignee),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "assigneeId",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Assignee ID" />
        ),
        cell: ({ row }) => renderUserId(row.original.assignee?.id ?? null),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "tags",
        accessorKey: "tags",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Tags" />
        ),
        cell: ({ row }) => renderTags(row.original.tags),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "byteSize",
        accessorKey: "byteSize",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Bytes" />
        ),
        cell: ({ row }) => formatBytes(row.getValue<number>("byteSize")),
        enableHiding: true,
      },
      {
        id: "sizeLabel",
        accessorKey: "sizeLabel",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Size" />
        ),
        cell: ({ row }) => row.getValue<string>("sizeLabel") || "-",
        enableSorting: false,
      },
      {
        id: "queueState",
        accessorKey: "queueState",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Queue State" />
        ),
        cell: ({ row }) => row.getValue<string | null>("queueState") ?? "-",
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "queueReason",
        accessorKey: "queueReason",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Queue Reason" />
        ),
        cell: ({ row }) => row.getValue<string | null>("queueReason") ?? "-",
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "mappingHealth",
        accessorKey: "mappingHealth",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Mapping" />
        ),
        cell: ({ row }) => renderMappingHealth(row.original.mappingHealth),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "createdAt",
        accessorKey: "createdAt",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Created" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("createdAt")),
        meta: {
          label: "Created",
          variant: "date",
        },
        enableColumnFilter: true,
        enableHiding: false,
      },
      {
        id: "updatedAt",
        accessorKey: "updatedAt",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Updated" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("updatedAt")),
        enableHiding: true,
      },
      {
        id: "activityAt",
        accessorKey: "activityAt",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Activity" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("activityAt")),
        enableHiding: true,
      },
      {
        id: "lastRun",
        accessorKey: "lastRun",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Last Run" />
        ),
        cell: ({ row }) => renderRunSummary(row.original.lastRun),
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "lastSuccessfulRun",
        accessorKey: "lastSuccessfulRun",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Last Success" />
        ),
        cell: ({ row }) => renderRunSummary(row.original.lastSuccessfulRun),
        enableSorting: false,
        enableHiding: true,
      },
    ],
    [fileTypeOptions, statusOptions],
  );

  const { table, debounceMs, throttleMs, shallow, history, startTransition } = useDataTable({
    data,
    columns,
    pageCount,
    initialState: {
      sorting: [{ id: "createdAt", desc: true }],
      pagination: { pageSize: DEFAULT_PAGE_SIZE },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  const isRowExpanded = useCallback(
    (row: Row<DocumentListRow>) => row.id === expandedRowId,
    [expandedRowId],
  );

  const onRowClick = useCallback(
    (row: Row<DocumentListRow>, event: MouseEvent<HTMLTableRowElement>) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("button, a, input, [role='button']")) {
        return;
      }
      setExpandedRowId((current) => (current === row.id ? null : row.id));
    },
    [],
  );

  return (
    <DataTable
      table={table}
      onRowClick={onRowClick}
      isRowExpanded={isRowExpanded}
      renderExpandedRow={(row) => {
        if (!PREVIEWABLE_FILE_TYPES.has(row.original.fileType)) {
          return (
            <div className="p-3 text-muted-foreground text-sm">
              Preview not available for this file type.
            </div>
          );
        }
        return <TablecnDocumentPreviewGrid document={row.original} />;
      }}
    >
      <DataTableAdvancedToolbar table={table}>
        <DataTableSortList table={table} align="start" />
        <DataTableFilterList
          table={table}
          align="start"
          debounceMs={debounceMs}
          throttleMs={throttleMs}
          shallow={shallow}
          history={history}
          startTransition={startTransition}
        />
      </DataTableAdvancedToolbar>
    </DataTable>
  );
}

function renderTags(tags?: string[]) {
  if (!tags || tags.length === 0) {
    return <span className="text-muted-foreground">-</span>;
  }

  const visible = tags.slice(0, 3);
  const remaining = tags.length - visible.length;

  return (
    <div className="flex items-center gap-1">
      {visible.map((tag) => (
        <Badge key={tag} variant="secondary">
          {tag}
        </Badge>
      ))}
      {remaining > 0 ? (
        <span className="text-xs text-muted-foreground">+{remaining}</span>
      ) : null}
    </div>
  );
}

function renderMappingHealth(mapping: DocumentListRow["mappingHealth"]) {
  const pendingOnly =
    Boolean(mapping.pending) && mapping.attention === 0 && mapping.unmapped === 0;
  if (!pendingOnly && mapping.attention === 0 && mapping.unmapped === 0) {
    return <span className="text-muted-foreground">OK</span>;
  }
  return <MappingBadge mapping={mapping} showPending />;
}

function renderRunSummary(run: DocumentListRow["lastRun"] | null | undefined) {
  if (!run) {
    return <span className="text-muted-foreground">-</span>;
  }

  const timestamp = run.runAt ? formatTimestamp(run.runAt) : "-";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="capitalize">{run.status}</span>
      <span className="text-xs text-muted-foreground">{timestamp}</span>
    </div>
  );
}

function renderUserSummary(user: DocumentListRow["uploader"]) {
  if (!user) {
    return <span className="text-muted-foreground">-</span>;
  }

  const primary = user.name ?? user.email ?? "Unknown";
  const secondary = user.name ? user.email : null;

  return (
    <div className="flex flex-col gap-0.5">
      <span>{primary}</span>
      {secondary ? (
        <span className="text-xs text-muted-foreground">{secondary}</span>
      ) : null}
    </div>
  );
}

function renderUserId(value: string | null) {
  if (!value) {
    return <span className="text-muted-foreground">-</span>;
  }
  return (
    <span className="font-mono text-xs text-muted-foreground" title={value}>
      {shortId(value)}
    </span>
  );
}
