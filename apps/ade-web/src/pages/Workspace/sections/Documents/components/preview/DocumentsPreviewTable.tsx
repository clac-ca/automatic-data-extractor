import { useEffect, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";

import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getCommonPinningStyles } from "@/lib/data-table";

import { DocumentsPreviewSkeleton } from "./DocumentsPreviewSkeleton";
import { useDocumentPreview } from "../../hooks/useDocumentPreview";
import { useRunOutputPreview } from "../../hooks/useRunOutputPreview";
import { columnLabel } from "../../utils";
import type { DocumentRow } from "../../types";

const DEFAULT_PAGE_SIZE = 25;
type PreviewSource = "output" | "original";

export function DocumentsPreviewTable({
  workspaceId,
  document,
  onDownloadOriginal,
  onDownloadOutput,
}: {
  workspaceId: string;
  document: DocumentRow;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onDownloadOutput?: (document: DocumentRow) => void;
}) {
  const outputRunId = document.lastSuccessfulRun?.id ?? null;
  const hasOutput = Boolean(outputRunId);
  const [previewSource, setPreviewSource] = useState<PreviewSource>(
    hasOutput ? "output" : "original",
  );
  const [sheetIndex, setSheetIndex] = useState<number | null>(null);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: DEFAULT_PAGE_SIZE });

  useEffect(() => {
    setSheetIndex(null);
    setPreviewSource(hasOutput ? "output" : "original");
  }, [document.id, hasOutput]);

  const inputPreview = useDocumentPreview({
    workspaceId,
    documentId: document.id,
    sheetIndex,
    enabled: previewSource === "original",
  });

  const outputPreview = useRunOutputPreview({
    runId: outputRunId,
    sheetIndex,
    enabled: previewSource === "output",
  });

  const previewState = previewSource === "output" ? outputPreview : inputPreview;
  const {
    sheets,
    activeSheet,
    preview,
    isSheetsLoading,
    sheetsError,
    isPreviewLoading,
    isPreviewFetching,
    previewError,
  } = previewState;

  useEffect(() => {
    if (sheetIndex !== null) return;
    if (!activeSheet) return;
    setSheetIndex(activeSheet.index);
  }, [activeSheet, sheetIndex]);

  useEffect(() => {
    setPagination((current) => ({ ...current, pageIndex: 0 }));
  }, [sheetIndex]);

  const handlePreviewSourceChange = (nextSource: PreviewSource) => {
    if (nextSource === previewSource) return;
    setSheetIndex(null);
    setPreviewSource(nextSource);
  };

  const columns = useMemo<ColumnDef<string[]>[]>(() => {
    if (!preview?.headers?.length) return [];
    return preview.headers.map((header: string, index: number) => ({
      id: `col_${index}`,
      header: () => (
        <span className="text-xs font-semibold">
          {header || columnLabel(index)}
        </span>
      ),
      cell: ({ row }: { row: { original: string[] } }) => (
        <div className="min-w-0 whitespace-nowrap text-xs">
          {row.original[index] ?? ""}
        </div>
      ),
      size: 160,
      minSize: 120,
      enableSorting: false,
      enableHiding: false,
    }));
  }, [preview?.headers]);

  const data = preview?.rows ?? [];

  const table = useReactTable({
    data,
    columns,
    state: { pagination },
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    enableRowSelection: false,
    manualPagination: false,
  });

  const visibleRows = preview?.rows?.length ?? 0;
  const totalRows = preview?.totalRows ?? 0;
  const totalColumns = preview?.totalColumns ?? 0;
  const visibleColumns = preview?.headers?.length ?? 0;
  const truncatedRows = preview?.truncatedRows ?? false;
  const truncatedColumns = preview?.truncatedColumns ?? false;

  const summaryLabel = preview
    ? `Showing ${visibleRows} of ${totalRows} rows · ${visibleColumns} of ${totalColumns} columns`
    : "Preparing preview";

  const truncationLabel =
    preview && (truncatedRows || truncatedColumns)
      ? "Preview is truncated"
      : null;

  const showSkeleton = (isSheetsLoading || isPreviewLoading) && !preview;
  const showRefreshing = Boolean(preview) && isPreviewFetching;

  const showError = Boolean(previewError || sheetsError);

  const hasSheets = sheets.length > 0;
  const selectedSheetValue = sheetIndex !== null ? String(sheetIndex) : "";
  const showOutputNotice = !hasOutput;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-background px-3 py-2 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-3">
          <PreviewSourceToggle
            value={previewSource}
            onChange={handlePreviewSourceChange}
            hasOutput={hasOutput}
          />
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-muted-foreground">Sheet</span>
            <Select
              value={selectedSheetValue}
              onValueChange={(value) => setSheetIndex(Number(value))}
              disabled={!hasSheets}
            >
              <SelectTrigger className="h-7 w-[180px] bg-background text-xs">
                <SelectValue placeholder={hasSheets ? "Select sheet" : "No sheets"} />
              </SelectTrigger>
              <SelectContent>
                {sheets.map((sheet) => (
                  <SelectItem key={sheet.index} value={String(sheet.index)}>
                    {sheet.name || `Sheet ${sheet.index + 1}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span>{summaryLabel}</span>
          {truncationLabel ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              {truncationLabel}
            </span>
          ) : null}
          {showOutputNotice ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              No normalized output yet
            </span>
          ) : null}
          {showRefreshing ? (
            <span className="text-[10px] text-muted-foreground">Refreshing…</span>
          ) : null}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {onDownloadOriginal ? (
            <Button size="sm" variant="outline" onClick={() => onDownloadOriginal(document)}>
              Download original
            </Button>
          ) : null}
          {onDownloadOutput && document.lastSuccessfulRun ? (
            <Button size="sm" variant="outline" onClick={() => onDownloadOutput(document)}>
              Download output
            </Button>
          ) : null}
        </div>
      </div>
      <div className="min-h-0 flex-1">
        {showSkeleton ? (
          <DocumentsPreviewSkeleton columnCount={Math.max(4, visibleColumns || 6)} />
        ) : showError ? (
          <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
            Unable to load the document preview. Try again later.
          </div>
        ) : preview ? (
          <div className="flex min-h-0 flex-1 flex-col gap-2.5">
            <div className="min-h-0 flex-1 overflow-hidden rounded-md border">
              <ScrollArea className="h-full w-full">
                <table
                  className="w-full caption-bottom text-sm"
                  style={{ width: table.getTotalSize(), minWidth: "100%" }}
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
                            }}
                          >
                            {header.isPlaceholder
                              ? null
                              : flexRender(header.column.columnDef.header, header.getContext())}
                          </TableHead>
                        ))}
                      </TableRow>
                    ))}
                  </TableHeader>
                  <TableBody>
                    {table.getRowModel().rows?.length ? (
                      table.getRowModel().rows.map((row) => (
                        <TableRow key={row.id} data-state={row.getIsSelected() && "selected"}>
                          {row.getVisibleCells().map((cell) => (
                            <TableCell
                              key={cell.id}
                              style={{
                                ...getCommonPinningStyles({ column: cell.column }),
                              }}
                            >
                              {flexRender(cell.column.columnDef.cell, cell.getContext())}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell
                          colSpan={table.getAllColumns().length}
                          className="h-24 text-center"
                        >
                          No results.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </table>
                <ScrollBar orientation="horizontal" />
              </ScrollArea>
            </div>
            <DataTablePagination table={table} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
            Preview not available for this document.
          </div>
        )}
      </div>
    </div>
  );
}

function PreviewSourceToggle({
  value,
  onChange,
  hasOutput,
}: {
  value: PreviewSource;
  onChange: (value: PreviewSource) => void;
  hasOutput: boolean;
}) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-border bg-muted/40 p-0.5">
      <Button
        size="sm"
        variant={value === "output" ? "secondary" : "ghost"}
        className="h-6 rounded-full px-2 text-[11px]"
        onClick={() => onChange("output")}
        disabled={!hasOutput}
        title={hasOutput ? "Preview normalized output" : "No normalized output available yet"}
      >
        Normalized
      </Button>
      <Button
        size="sm"
        variant={value === "original" ? "secondary" : "ghost"}
        className="h-6 rounded-full px-2 text-[11px]"
        onClick={() => onChange("original")}
      >
        Original
      </Button>
    </div>
  );
}
