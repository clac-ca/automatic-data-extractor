import { flexRender, type Column, type Row, type Table as TanstackTable } from "@tanstack/react-table";
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
  stretchColumnId?: string;
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
  stretchColumnId,
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
  const baseTableWidth = Math.max(1, table.getTotalSize());
  const virtualizeEnabled = Boolean(virtualize?.enabled);
  const onRangeChange = virtualize?.onRangeChange;
  const [containerWidth, setContainerWidth] = React.useState<number | null>(null);
  const columnSizing = table.getState().columnSizing ?? {};
  const hasManualSizing = Object.keys(columnSizing).length > 0;

  React.useEffect(() => {
    const element = virtualize?.getScrollElement?.() ?? containerRef.current;
    if (!element) return;

    const updateWidth = () => {
      setContainerWidth(element.clientWidth);
    };
    updateWidth();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => updateWidth());
    observer.observe(element);
    return () => observer.disconnect();
  }, [virtualize?.getScrollElement]);

  const canStretch =
    Boolean(stretchColumnId) &&
    !hasManualSizing &&
    typeof containerWidth === "number" &&
    containerWidth > baseTableWidth;
  const extraWidth = canStretch && containerWidth ? containerWidth - baseTableWidth : 0;
  const tableWidth = baseTableWidth + extraWidth;
  const resolveColumnWidth = React.useCallback(
    (column: Column<TData>, size: number) => {
      if (canStretch && column.id === stretchColumnId) {
        return size + extraWidth;
      }
      return size;
    },
    [canStretch, extraWidth, stretchColumnId],
  );

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
        <Table
          style={{
            width: tableWidth,
            minWidth: tableWidth,
          }}
        >
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    style={{
                      ...getCommonPinningStyles({ column: header.column }),
                      width: resolveColumnWidth(header.column, header.getSize()),
                      minWidth: header.column.columnDef.minSize,
                      maxWidth: header.column.columnDef.maxSize,
                    }}
                    className="relative"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                    {header.column.getCanResize() ? (
                      <div
                        role="separator"
                        tabIndex={-1}
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        onDoubleClick={() => header.column.resetSize()}
                        className={cn(
                          "absolute right-0 top-0 h-full w-2 cursor-col-resize touch-none select-none hover:bg-border/70",
                          header.column.getIsResizing() && "bg-ring/40",
                        )}
                      />
                    ) : null}
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
                              width: resolveColumnWidth(cell.column, cell.column.getSize()),
                              minWidth: cell.column.columnDef.minSize,
                              maxWidth: cell.column.columnDef.maxSize,
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
