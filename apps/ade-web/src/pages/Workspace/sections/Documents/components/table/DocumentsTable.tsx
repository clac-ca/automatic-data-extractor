import type { ReactNode } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { useDataTable } from "@/hooks/use-data-table";
import {
  ActionBar,
  ActionBarGroup,
  ActionBarItem,
  ActionBarSelection,
  ActionBarSeparator,
} from "@/components/ui/action-bar";
import { Button } from "@/components/ui/button";

import { DEFAULT_PAGE_SIZE, DEFAULT_SORTING } from "../../constants";
import type { DocumentRow } from "../../types";

interface DocumentsTableProps {
  data: DocumentRow[];
  columns: ColumnDef<DocumentRow>[];
  pageCount: number;
  filterMode: "simple" | "advanced";
  onToggleFilterMode?: () => void;
  toolbarActions?: ReactNode;
}

export function DocumentsTable({
  data,
  columns,
  pageCount,
  filterMode,
  onToggleFilterMode,
  toolbarActions,
}: DocumentsTableProps) {
  const isAdvanced = filterMode === "advanced";
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
        lastRunAt: false,
        hasOutput: false,
        createdAt: false,
        updatedAt: false,
        lastSuccessfulRun: false,
      },
      columnPinning: { left: ["select"], right: ["actions"] },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: isAdvanced,
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

  const filterToggle = onToggleFilterMode ? (
    <Button variant="outline" size="sm" onClick={onToggleFilterMode}>
      {isAdvanced ? "Simple filters" : "Advanced filters"}
    </Button>
  ) : null;

  const toolbarTail = filterToggle || toolbarActions ? (
    <div className="ml-auto flex flex-wrap items-center gap-2">
      {filterToggle}
      {toolbarActions}
    </div>
  ) : null;

  return (
    <div className="flex flex-col gap-3">
      {isAdvanced ? (
        <DataTableAdvancedToolbar table={table}>
          <DataTableSortList table={table} align="start" />
          <DataTableFilterList
            table={table}
            align="start"
            debounceMs={debounceMs}
            throttleMs={throttleMs}
            shallow={shallow}
          />
          {toolbarTail}
        </DataTableAdvancedToolbar>
      ) : (
        <DataTableToolbar table={table}>
          <DataTableSortList table={table} align="start" />
          {filterToggle}
          {toolbarActions}
        </DataTableToolbar>
      )}
      <DataTable table={table} actionBar={actionBar} />
    </div>
  );
}
