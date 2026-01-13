import type { ReactNode } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { useDataTable } from "@/hooks/use-data-table";
import {
  ActionBar,
  ActionBarGroup,
  ActionBarItem,
  ActionBarSelection,
  ActionBarSeparator,
} from "@/components/ui/action-bar";

import { DEFAULT_PAGE_SIZE, DEFAULT_SORTING } from "../../constants";
import type { DocumentRow } from "../../types";

interface DocumentsTableProps {
  data: DocumentRow[];
  columns: ColumnDef<DocumentRow>[];
  pageCount: number;
  toolbarActions?: ReactNode;
}

export function DocumentsTable({
  data,
  columns,
  pageCount,
  toolbarActions,
}: DocumentsTableProps) {
  const { table, debounceMs, throttleMs, shallow } = useDataTable({
    data,
    columns,
    pageCount,
    enableColumnResizing: true,
    defaultColumn: {
      size: 140,
      minSize: 90,
    },
    initialState: {
      sorting: DEFAULT_SORTING,
      pagination: { pageIndex: 0, pageSize: DEFAULT_PAGE_SIZE },
      columnVisibility: {
        select: true,
        id: false,
        fileType: false,
        uploaderId: false,
        byteSize: false,
        runStatus: false,
        hasOutput: false,
        createdAt: false,
        updatedAt: false,
        latestSuccessfulRun: false,
      },
      columnPinning: { left: ["select"], right: ["actions"] },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  const selectedCount = table.getFilteredSelectedRowModel().rows.length;
  const actionBar = (
    <ActionBar
      open={selectedCount > 0}
      onOpenChange={(open) => {
        if (!open) {
          table.toggleAllRowsSelected(false);
        }
      }}
    >
      <ActionBarSelection>{selectedCount} selected</ActionBarSelection>
      <ActionBarSeparator />
      <ActionBarGroup>
        <ActionBarItem variant="outline" size="sm" onSelect={() => table.toggleAllRowsSelected(false)}>
          Clear selection
        </ActionBarItem>
      </ActionBarGroup>
    </ActionBar>
  );

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
      <DataTable table={table} actionBar={actionBar} />
    </div>
  );
}
