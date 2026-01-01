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
import { fileTypeLabel } from "@pages/Workspace/sections/Documents/utils";
import { TablecnDocumentPreviewGrid } from "./TablecnDocumentPreviewGrid";
import type { DocumentListRow } from "../types";
import { DEFAULT_PAGE_SIZE, formatTimestamp } from "../utils";

interface TablecnDocumentsTableProps {
  data: DocumentListRow[];
  pageCount: number;
}

const PREVIEWABLE_FILE_TYPES = new Set<FileType>(["xlsx", "xls", "csv"]);

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
    ],
    [fileTypeOptions, statusOptions],
  );

  const { table, debounceMs, throttleMs, shallow } = useDataTable({
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
        />
      </DataTableAdvancedToolbar>
    </DataTable>
  );
}
