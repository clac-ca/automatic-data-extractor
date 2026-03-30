import { useRef } from "react";
import { flexRender, type Row, type Table as TanstackTable } from "@tanstack/react-table";
import type * as React from "react";

import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import {
  getRowPointerIntent,
  shouldActivateRowFromClick,
  shouldActivateRowFromKeyboard,
  shouldOpenRowContextMenu,
  shouldOpenRowContextMenuFromKeyboard,
  type RowPointerIntent,
} from "@/components/data-table/rowInteraction";
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
  pageSizeOptions?: number[];
  onRowActivate?: (row: Row<TData>) => void;
  onRowContextMenu?: (row: Row<TData>, position: { x: number; y: number }) => void;
}

export function DataTable<TData>({
  table,
  actionBar,
  pageSizeOptions,
  onRowActivate,
  onRowContextMenu,
  children,
  className,
  ...props
}: DataTableProps<TData>) {
  const pointerIntentRef = useRef<Map<string, RowPointerIntent>>(new Map());

  const getPointerIntent = (row: Row<TData>) => pointerIntentRef.current.get(row.id) ?? null;

  const clearPointerIntent = (row: Row<TData>) => {
    pointerIntentRef.current.delete(row.id);
  };

  const handleRowClick = (row: Row<TData>, event: React.MouseEvent<HTMLTableRowElement>) => {
    const pointerIntent = getPointerIntent(row);
    clearPointerIntent(row);
    if (!onRowActivate) return;
    if (!shouldActivateRowFromClick(event, pointerIntent)) return;
    onRowActivate(row);
  };

  const handleRowContextMenu = (
    row: Row<TData>,
    event: React.MouseEvent<HTMLTableRowElement>,
  ) => {
    clearPointerIntent(row);
    if (!onRowContextMenu) return;
    if (!shouldOpenRowContextMenu(event)) return;
    event.preventDefault();
    event.stopPropagation();
    onRowContextMenu(row, { x: event.clientX, y: event.clientY });
  };

  const handleRowKeyDown = (row: Row<TData>, event: React.KeyboardEvent<HTMLTableRowElement>) => {
    if (onRowContextMenu && shouldOpenRowContextMenuFromKeyboard(event)) {
      event.preventDefault();
      const rect = event.currentTarget.getBoundingClientRect();
      onRowContextMenu(row, {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
      });
      return;
    }

    if (!onRowActivate) return;
    if (!shouldActivateRowFromKeyboard(event)) return;
    event.preventDefault();
    onRowActivate(row);
  };

  const tableWidth = Math.max(table.getTotalSize(), 1);

  return (
    <div
      className={cn("flex w-full flex-col gap-2.5 overflow-auto", className)}
      {...props}
    >
      {children}
      <div className="overflow-hidden rounded-md border">
        <Table className="table-fixed" style={{ width: `${tableWidth}px` }}>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className={cn(
                      "relative",
                      (header.column.columnDef.meta as { headerClassName?: string } | undefined)
                        ?.headerClassName,
                    )}
                    style={{
                      width: `${header.getSize()}px`,
                      minWidth: `${header.getSize()}px`,
                      ...getCommonPinningStyles({ column: header.column }),
                    }}
                  >
                    {header.isPlaceholder ? null : (
                      <>
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getCanResize() ? (
                          <button
                            type="button"
                            tabIndex={-1}
                            data-column-resize-handle
                            onDoubleClick={() => header.column.resetSize()}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                            }}
                            onMouseDown={header.getResizeHandler()}
                            onTouchStart={header.getResizeHandler()}
                            aria-label={`Resize ${String(header.column.columnDef.meta?.label ?? header.column.id)} column`}
                            className={cn(
                              "absolute right-0 top-0 h-full w-2 cursor-col-resize touch-none select-none border-0 bg-transparent p-0 transition-colors",
                              header.column.getIsResizing()
                                ? "bg-border"
                                : "hover:bg-border/70",
                            )}
                          />
                        ) : null}
                      </>
                    )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  tabIndex={onRowActivate || onRowContextMenu ? 0 : undefined}
                  onPointerDownCapture={(event) => {
                    pointerIntentRef.current.set(row.id, getRowPointerIntent(event));
                  }}
                  onClick={(event) => handleRowClick(row, event)}
                  onContextMenuCapture={(event) => handleRowContextMenu(row, event)}
                  onKeyDown={(event) => handleRowKeyDown(row, event)}
                  className={cn(
                    "documents-table-row",
                    (onRowActivate || onRowContextMenu) &&
                      "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn(
                        (cell.column.columnDef.meta as { cellClassName?: string } | undefined)
                          ?.cellClassName,
                      )}
                      style={{
                        width: `${cell.column.getSize()}px`,
                        minWidth: `${cell.column.getSize()}px`,
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
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={table.getVisibleLeafColumns().length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex flex-col gap-2.5">
        <DataTablePagination table={table} pageSizeOptions={pageSizeOptions} />
        {actionBar &&
          table.getFilteredSelectedRowModel().rows.length > 0 &&
          actionBar}
      </div>
    </div>
  );
}
