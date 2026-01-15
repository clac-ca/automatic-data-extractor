import { useEffect, useMemo, useState } from "react";
import { getCoreRowModel, getPaginationRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { DocumentsPreviewSkeleton } from "./DocumentsPreviewSkeleton";
import { useDocumentPreview } from "../../hooks/useDocumentPreview";
import { columnLabel } from "../../utils";
import type { DocumentRow } from "../../types";

const DEFAULT_PAGE_SIZE = 25;

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
  const [sheetIndex, setSheetIndex] = useState<number | null>(null);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: DEFAULT_PAGE_SIZE });

  useEffect(() => {
    setSheetIndex(null);
  }, [document.id]);

  const {
    sheets,
    activeSheet,
    preview,
    isSheetsLoading,
    sheetsError,
    isPreviewLoading,
    previewError,
  } = useDocumentPreview({
    workspaceId,
    documentId: document.id,
    sheetIndex,
  });

  useEffect(() => {
    if (sheetIndex !== null) return;
    if (!activeSheet) return;
    setSheetIndex(activeSheet.index);
  }, [activeSheet, sheetIndex]);

  useEffect(() => {
    setPagination((current) => ({ ...current, pageIndex: 0 }));
  }, [sheetIndex]);

  const columns = useMemo<ColumnDef<string[]>[]>(() => {
    if (!preview?.headers?.length) return [];
    return preview.headers.map((header, index) => ({
      id: `col_${index}`,
      header: () => (
        <span className="text-xs font-semibold">
          {header || columnLabel(index)}
        </span>
      ),
      cell: ({ row }) => (
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
  const showRefreshing = Boolean(preview) && isPreviewLoading;

  const showError = Boolean(previewError || sheetsError);

  const hasSheets = sheets.length > 0;
  const selectedSheetValue = sheetIndex !== null ? String(sheetIndex) : "";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-background px-3 py-2 text-xs text-muted-foreground">
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
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span>{summaryLabel}</span>
          {truncationLabel ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              {truncationLabel}
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
          <DataTable table={table} className="h-full" />
        ) : (
          <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
            Preview not available for this document.
          </div>
        )}
      </div>
    </div>
  );
}
