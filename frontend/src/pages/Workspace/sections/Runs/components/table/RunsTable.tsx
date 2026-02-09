import type { ReactNode } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { useDataTable } from "@/hooks/use-data-table";

import { DEFAULT_PAGE_SIZE } from "../../constants";
import type { RunRecord } from "../../types";

interface RunsTableProps {
  data: RunRecord[];
  columns: ColumnDef<RunRecord>[];
  pageCount: number;
  toolbarActions?: ReactNode;
}

export function RunsTable({
  data,
  columns,
  pageCount,
  toolbarActions,
}: RunsTableProps) {
  const { table, debounceMs, throttleMs, shallow } = useDataTable({
    data,
    columns,
    pageCount,
    initialState: {
      sorting: [{ id: "createdAt", desc: true }],
      pagination: { pageIndex: 0, pageSize: DEFAULT_PAGE_SIZE },
      columnVisibility: {
        id: false,
        startedAt: false,
        completedAt: false,
        fileType: false,
        hasOutput: false,
      },
      columnPinning: { right: ["actions"] },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <DataTableAdvancedToolbar table={table}>
        <DataTableSortList table={table} align="start" />
        <DataTableFilterList
          table={table}
          align="start"
          debounceMs={debounceMs}
          throttleMs={throttleMs}
          shallow={shallow}
        />
        {toolbarActions ? (
          <div className="ml-auto flex flex-wrap items-center gap-2">{toolbarActions}</div>
        ) : null}
      </DataTableAdvancedToolbar>
      <DataTable table={table} />
    </div>
  );
}
