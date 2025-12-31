import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@components/tablecn/data-table/data-table";
import { DataTableColumnHeader } from "@components/tablecn/data-table/data-table-column-header";
import { useDataTable } from "@components/tablecn/hooks/use-data-table";
import { Badge } from "@components/tablecn/ui/badge";
import type { DocumentListRow } from "@pages/Documents/types";
import { fileTypeLabel } from "@pages/Documents/utils";
import { DEFAULT_PAGE_SIZE, formatTimestamp } from "../utils";

interface TablecnDocumentsTableProps {
  data: DocumentListRow[];
  pageCount: number;
}

export function TablecnDocumentsTable({
  data,
  pageCount,
}: TablecnDocumentsTableProps) {
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

  const { table } = useDataTable({
    data,
    columns,
    pageCount,
    initialState: {
      pagination: { pageSize: DEFAULT_PAGE_SIZE },
    },
    getRowId: (row) => row.id,
  });

  return <DataTable table={table} />;
}
