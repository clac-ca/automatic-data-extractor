import { flexRender, type Row, type Table as TanstackTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import * as React from "react";

import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getCommonPinningStyles } from "@/lib/data-table";
import { cn } from "@/lib/utils";

interface DataTableProps<TData> extends React.ComponentProps<"div"> {
  table: TanstackTable<TData>;
  actionBar?: React.ReactNode;
  showPagination?: boolean;
  onRowClick?: (row: Row<TData>, event: React.MouseEvent<HTMLTableRowElement>) => void;
  onRowContextMenu?: (row: Row<TData>, event: React.MouseEvent<HTMLTableRowElement>) => void;
  isRowExpanded?: (row: Row<TData>) => boolean;
  renderExpandedRow?: (row: Row<TData>) => React.ReactNode;
  expandedRowCellClassName?: string;
  virtualize?: {
    enabled?: boolean;
    estimateSize?: number;
    overscan?: number;
    getScrollElement?: () => HTMLElement | null;
    onRangeChange?: (range: { startIndex: number; endIndex: number; total: number }) => void;
  };
}

export function DataTable<TData>({
  table,
  actionBar,
  showPagination = true,
  onRowClick,
  onRowContextMenu,
  isRowExpanded,
  renderExpandedRow,
  expandedRowCellClassName,
  virtualize,
  children,
  className,
  ...props
}: DataTableProps<TData>) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const rows = showPagination
    ? table.getRowModel().rows
    : table.getPrePaginationRowModel().rows;
  const visibleColumnCount = Math.max(1, table.getVisibleLeafColumns().length);
  const virtualizeEnabled = Boolean(virtualize?.enabled);
  const onRangeChange = virtualize?.onRangeChange;

  const rowVirtualizer = useVirtualizer({
    count: virtualizeEnabled ? rows.length : 0,
    getScrollElement: virtualize?.getScrollElement ?? (() => containerRef.current),
    estimateSize: () => virtualize?.estimateSize ?? 44,
    overscan: virtualize?.overscan ?? 8,
  });
  const virtualRows = virtualizeEnabled ? rowVirtualizer.getVirtualItems() : [];
  const virtualPaddingTop = virtualizeEnabled ? (virtualRows[0]?.start ?? 0) : 0;
  const virtualPaddingBottom = virtualizeEnabled
    ? rowVirtualizer.getTotalSize() - (virtualRows[virtualRows.length - 1]?.end ?? 0)
    : 0;

  React.useEffect(() => {
    if (!virtualizeEnabled || !onRangeChange) {
      return;
    }
    const total = rows.length;
    if (!virtualRows.length) {
      onRangeChange({ startIndex: 0, endIndex: -1, total });
      return;
    }
    onRangeChange({
      startIndex: virtualRows[0].index,
      endIndex: virtualRows[virtualRows.length - 1].index,
      total,
    });
  }, [onRangeChange, rows.length, virtualRows, virtualizeEnabled]);

  return (
    <div
      className={cn("flex min-w-0 w-full flex-col gap-2.5 overflow-auto", className)}
      {...props}
      ref={containerRef}
    >
      {children}
      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    style={{
                      ...getCommonPinningStyles({ column: header.column }),
                    }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows?.length ? (
              <>
                {virtualizeEnabled && virtualPaddingTop > 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={visibleColumnCount}
                      style={{ height: `${virtualPaddingTop}px` }}
                    />
                  </TableRow>
                ) : null}
                {(virtualizeEnabled ? virtualRows.map((virtualRow) => rows[virtualRow.index]) : rows).map((row) => {
                  const expanded = isRowExpanded?.(row) ?? false;
                  return (
                    <React.Fragment key={row.id}>
                      <TableRow
                        data-state={row.getIsSelected() && "selected"}
                        data-expanded={expanded || undefined}
                        aria-expanded={expanded || undefined}
                        className={cn(onRowClick && "cursor-pointer")}
                        onClick={onRowClick ? (event) => onRowClick(row, event) : undefined}
                        onContextMenu={
                          onRowContextMenu ? (event) => onRowContextMenu(row, event) : undefined
                        }
                      >
                        {row.getVisibleCells().map((cell) => (
                          <TableCell
                            key={cell.id}
                            style={{
                              ...getCommonPinningStyles({ column: cell.column }),
                            }}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                      {renderExpandedRow && expanded && (
                        <TableRow>
                          <TableCell
                            colSpan={visibleColumnCount}
                            className={cn("bg-muted/20", expandedRowCellClassName)}
                          >
                            {renderExpandedRow(row)}
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  );
                })}
                {virtualizeEnabled && virtualPaddingBottom > 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={visibleColumnCount}
                      style={{ height: `${virtualPaddingBottom}px` }}
                    />
                  </TableRow>
                ) : null}
              </>
            ) : (
              <TableRow>
                <TableCell
                  colSpan={visibleColumnCount}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {(showPagination || actionBar) && (
        <div className="flex flex-col gap-2.5">
          {showPagination ? <DataTablePagination table={table} /> : null}
          {actionBar &&
            table.getFilteredSelectedRowModel().rows.length > 0 &&
            actionBar}
        </div>
      )}
    </div>
  );
}
