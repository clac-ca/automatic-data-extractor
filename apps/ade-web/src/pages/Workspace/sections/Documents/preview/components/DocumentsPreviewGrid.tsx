import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataGrid } from "@/components/data-grid/data-grid";
import { DataGridFilterMenu } from "@/components/data-grid/data-grid-filter-menu";
import { DataGridKeyboardShortcuts } from "@/components/data-grid/data-grid-keyboard-shortcuts";
import { DataGridRowHeightMenu } from "@/components/data-grid/data-grid-row-height-menu";
import { DataGridSortMenu } from "@/components/data-grid/data-grid-sort-menu";
import { DataGridViewMenu } from "@/components/data-grid/data-grid-view-menu";
import { useDataGrid } from "@/hooks/use-data-grid";
import { useWindowSize } from "@/hooks/use-window-size";
import { getFilterFn } from "@/lib/data-grid-filters";

import { columnLabel } from "../../utils";

type DocumentsPreviewGridProps = {
  headerRow: string[];
  rows: string[][];
  columnCount: number;
  resetKey: string;
};

export function DocumentsPreviewGrid({
  headerRow,
  rows,
  columnCount,
  resetKey,
}: DocumentsPreviewGridProps) {
  const windowSize = useWindowSize({ defaultHeight: 720 });

  const filterFn = useMemo(() => getFilterFn<string[]>(), []);

  const columns = useMemo<ColumnDef<string[]>[]>(() => {
    if (!columnCount) return [];

    return Array.from({ length: columnCount }, (_, index) => {
      const header = headerRow[index] ?? "";
      const label = header.trim() ? header : columnLabel(index);

      return {
        id: `col_${index}`,
        accessorFn: (row) => row[index] ?? "",
        header: label,
        meta: {
          label,
          cell: {
            variant: "short-text",
          },
        },
        minSize: 120,
        filterFn,
      };
    });
  }, [columnCount, filterFn, headerRow]);

  const { table, ...dataGridProps } = useDataGrid({
    data: rows,
    columns,
    readOnly: true,
    enableSearch: true,
    enableColumnVirtualization: true,
    getRowId: (_row, index) => `${resetKey}-${index}`,
  });

  const height = Math.max(400, windowSize.height - 150);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div
        role="toolbar"
        aria-orientation="horizontal"
        className="flex items-center gap-2 self-end"
      >
        <DataGridKeyboardShortcuts />
        <DataGridFilterMenu table={table} align="end" />
        <DataGridSortMenu table={table} align="end" />
        <DataGridRowHeightMenu table={table} align="end" />
        <DataGridViewMenu table={table} align="end" />
      </div>
      <DataGrid {...dataGridProps} table={table} height={height} />
    </div>
  );
}
