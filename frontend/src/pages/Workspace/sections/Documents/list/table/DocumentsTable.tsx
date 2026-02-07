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

import { DEFAULT_PAGE_SIZE, DEFAULT_SORTING } from "../../shared/constants";
import type { DocumentRow } from "../../shared/types";

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
        activityAt: false,
        lastRunPhase: true,
        lastRunAt: true,
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

  const toolbarShellClassName =
    "rounded-xl border border-border/60 bg-card/90 px-2 py-2 shadow-sm";
  const filterToggle = onToggleFilterMode ? (
    <Button variant="outline" size="sm" onClick={onToggleFilterMode}>
      {isAdvanced ? "Simple filters" : "Advanced filters"}
    </Button>
  ) : null;

  const toolbarTail = filterToggle || toolbarActions ? (
    <>
      {filterToggle}
      {toolbarActions}
    </>
  ) : null;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
      {isAdvanced ? (
        <DataTableAdvancedToolbar table={table} className={toolbarShellClassName}>
          <div className="flex w-full flex-wrap items-center gap-2">
            <div className="min-w-0 flex flex-wrap items-center gap-2">
              <DataTableSortList table={table} align="start" />
              <DataTableFilterList
                table={table}
                align="start"
                debounceMs={debounceMs}
                throttleMs={throttleMs}
                shallow={shallow}
              />
            </div>
            {toolbarTail ? (
              <div className="ml-auto min-w-0 flex flex-wrap items-center justify-end gap-2">
                {toolbarTail}
              </div>
            ) : null}
          </div>
        </DataTableAdvancedToolbar>
      ) : (
        <DataTableToolbar table={table} className={toolbarShellClassName}>
          <DataTableSortList table={table} align="start" />
          <div className="min-w-0 flex flex-wrap items-center justify-end gap-2">
            {filterToggle}
            {toolbarActions}
          </div>
        </DataTableToolbar>
      )}
      <DataTable
        table={table}
        actionBar={actionBar}
        className="documents-table min-h-0 min-w-0 flex-1 overflow-hidden"
      />
    </div>
  );
}
