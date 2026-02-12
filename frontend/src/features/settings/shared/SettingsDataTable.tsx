import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

import { useSettingsFocusRestore } from "./hooks/useSettingsFocusRestore";
import type { SettingsTableColumnSpec } from "./types";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

export function SettingsDataTable<T>({
  rows,
  columns,
  getRowId,
  onRowOpen,
  page,
  pageSize,
  totalCount,
  onPageChange,
  onPageSizeChange,
  focusStorageKey,
  openActionLabel = "Open",
  rowClassName,
}: {
  readonly rows: readonly T[];
  readonly columns: readonly SettingsTableColumnSpec<T>[];
  readonly getRowId: (row: T) => string;
  readonly onRowOpen?: (row: T) => void;
  readonly page: number;
  readonly pageSize: number;
  readonly totalCount: number;
  readonly onPageChange: (page: number) => void;
  readonly onPageSizeChange: (pageSize: number) => void;
  readonly focusStorageKey?: string;
  readonly openActionLabel?: string;
  readonly rowClassName?: string;
}) {
  const { rememberRow, focusKey } = useSettingsFocusRestore(focusStorageKey ?? "");

  const safePageSize = pageSize > 0 ? pageSize : 25;
  const totalPages = Math.max(1, Math.ceil(totalCount / safePageSize));
  const safePage = Math.min(Math.max(page, 1), totalPages);

  const pageRows = useMemo(() => {
    const start = (safePage - 1) * safePageSize;
    return rows.slice(start, start + safePageSize);
  }, [rows, safePage, safePageSize]);

  const startLabel = totalCount === 0 ? 0 : (safePage - 1) * safePageSize + 1;
  const endLabel = Math.min(totalCount, safePage * safePageSize);

  const handleRowOpen = (row: T) => {
    if (!onRowOpen) {
      return;
    }
    const rowId = getRowId(row);
    if (focusStorageKey) {
      rememberRow(rowId);
    }
    onRowOpen(row);
  };

  return (
    <div className="overflow-hidden rounded-xl border border-border/70">
      <Table>
        <TableHeader>
          <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {columns.map((column) => (
              <TableHead key={column.id} className={cn("px-4", column.headerClassName)}>
                {column.header}
              </TableHead>
            ))}
            {onRowOpen ? <TableHead className="px-4 text-right">Action</TableHead> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {pageRows.map((row) => {
            const rowId = getRowId(row);
            return (
              <TableRow
                key={rowId}
                data-settings-focus-key={focusKey || undefined}
                data-settings-row-id={focusKey ? rowId : undefined}
                tabIndex={onRowOpen ? 0 : undefined}
                className={cn(onRowOpen ? "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" : undefined, rowClassName)}
                onClick={() => handleRowOpen(row)}
                onKeyDown={(event) => {
                  if (!onRowOpen) {
                    return;
                  }
                  if (event.key !== "Enter" && event.key !== " ") {
                    return;
                  }
                  event.preventDefault();
                  handleRowOpen(row);
                }}
              >
                {columns.map((column) => (
                  <TableCell key={`${rowId}-${column.id}`} className={cn("px-4 py-3", column.cellClassName)}>
                    {column.cell(row)}
                  </TableCell>
                ))}
                {onRowOpen ? (
                  <TableCell className="px-4 py-3 text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRowOpen(row);
                      }}
                    >
                      {openActionLabel}
                    </Button>
                  </TableCell>
                ) : null}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 bg-muted/20 px-4 py-3">
        <p className="text-xs text-muted-foreground">
          Showing {startLabel}-{endLabel} of {totalCount}
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">Rows</span>
          <Select value={String(safePageSize)} onValueChange={(value) => onPageSizeChange(Number(value))}>
            <SelectTrigger className="h-8 w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((option) => (
                <SelectItem key={option} value={String(option)}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={safePage <= 1}
            onClick={() => onPageChange(safePage - 1)}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={safePage >= totalPages}
            onClick={() => onPageChange(safePage + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
