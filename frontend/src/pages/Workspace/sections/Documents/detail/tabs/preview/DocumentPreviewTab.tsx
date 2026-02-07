import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchDocumentPreview,
  fetchDocumentSheets,
  type WorkbookSheetPreview,
} from "@/api/documents";
import {
  fetchRunOutputPreview,
  fetchRunOutputSheets,
} from "@/api/runs/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  type DocumentPreviewSource,
} from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { getNormalizedPreviewState } from "./state";

const DEFAULT_MAX_ROWS = 200;
const DEFAULT_MAX_COLUMNS = 50;

type PreviewSheet = {
  name: string;
  index: number;
  is_active?: boolean;
};

function spreadsheetColumnLabel(index: number) {
  let label = "";
  let n = index + 1;
  while (n > 0) {
    const remainder = (n - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    n = Math.floor((n - 1) / 26);
  }
  return label;
}

function pickDefaultSheet(sheets: PreviewSheet[]) {
  if (sheets.length === 0) return null;
  return sheets.find((sheet) => sheet.is_active) ?? sheets[0];
}

function buildSheetLabel(sheet: PreviewSheet) {
  return sheet.name || `Sheet ${sheet.index + 1}`;
}

export function DocumentPreviewTab({
  workspaceId,
  document,
  source,
  sheet,
  onSourceChange,
  onSheetChange,
}: {
  workspaceId: string;
  document: DocumentRow;
  source: DocumentPreviewSource;
  sheet: string | null;
  onSourceChange: (source: DocumentPreviewSource) => void;
  onSheetChange: (sheet: string | null) => void;
}) {
  const normalizedState = getNormalizedPreviewState(document);
  const normalizedRunId =
    normalizedState.available && document.lastRun?.id
      ? document.lastRun.id
      : null;
  const canLoadSelectedSource =
    source === "original" || (source === "normalized" && Boolean(normalizedRunId));

  const sheetsQuery = useQuery<PreviewSheet[]>({
    queryKey: [
      "document-detail-preview-sheets",
      workspaceId,
      document.id,
      source,
      normalizedRunId,
    ],
    queryFn: ({ signal }) =>
      source === "original"
        ? fetchDocumentSheets(workspaceId, document.id, signal)
        : fetchRunOutputSheets(normalizedRunId as string, signal),
    enabled: Boolean(workspaceId && document.id && canLoadSelectedSource),
    staleTime: 30_000,
  });

  const sheets = sheetsQuery.data ?? [];
  const defaultSheet = useMemo(() => pickDefaultSheet(sheets), [sheets]);
  const selectedSheet = useMemo(() => {
    if (!sheets.length) return null;
    if (sheet) {
      const match = sheets.find((entry) => entry.name === sheet);
      if (match) return match;
    }
    return defaultSheet;
  }, [defaultSheet, sheet, sheets]);

  useEffect(() => {
    if (!canLoadSelectedSource) {
      return;
    }
    if (!sheets.length) {
      if (sheet) {
        onSheetChange(null);
      }
      return;
    }
    const nextSheet = selectedSheet?.name ?? null;
    if (nextSheet !== sheet) {
      onSheetChange(nextSheet);
    }
  }, [canLoadSelectedSource, onSheetChange, selectedSheet, sheet, sheets.length]);

  const previewQuery = useQuery<WorkbookSheetPreview>({
    queryKey: [
      "document-detail-preview-grid",
      workspaceId,
      document.id,
      source,
      normalizedRunId,
      selectedSheet?.index ?? null,
      DEFAULT_MAX_ROWS,
      DEFAULT_MAX_COLUMNS,
    ],
    queryFn: ({ signal }) => {
      const options = {
        maxRows: DEFAULT_MAX_ROWS,
        maxColumns: DEFAULT_MAX_COLUMNS,
        sheetIndex: selectedSheet?.index ?? undefined,
      };
      if (source === "original") {
        return fetchDocumentPreview(workspaceId, document.id, options, signal);
      }
      return fetchRunOutputPreview(normalizedRunId as string, options, signal);
    },
    enabled: Boolean(
      workspaceId &&
        document.id &&
        canLoadSelectedSource &&
        selectedSheet,
    ),
    staleTime: 30_000,
  });

  const previewRows = useMemo(
    () => previewQuery.data?.rows ?? [],
    [previewQuery.data],
  );

  const columnLabels = useMemo(() => {
    const fallbackColumnCount =
      typeof previewQuery.data?.totalColumns === "number"
        ? previewQuery.data.totalColumns
        : previewRows.reduce((max, row) => Math.max(max, row.length), 0);

    return Array.from({ length: fallbackColumnCount }, (_, index) =>
      spreadsheetColumnLabel(index),
    );
  }, [previewQuery.data?.totalColumns, previewRows]);

  const previewMeta = useMemo(() => {
    if (!previewQuery.data) return null;
    const { totalRows, totalColumns, truncatedRows, truncatedColumns } = previewQuery.data;
    if (typeof totalRows !== "number" || typeof totalColumns !== "number") return null;
    return {
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns,
    };
  }, [previewQuery.data]);

  const hasSheetError = sheetsQuery.isError;
  const hasPreviewError = previewQuery.isError;
  const isLoading = sheetsQuery.isLoading || previewQuery.isLoading;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-muted/10">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background px-4 py-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Preview</div>
          <div className="text-xs text-muted-foreground">{document.name}</div>
        </div>
        <div className="flex items-center gap-3">
          {previewMeta ? (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="bg-background">
                {previewMeta.totalRows.toLocaleString()} rows
              </Badge>
              <Badge variant="outline" className="bg-background">
                {previewMeta.totalColumns.toLocaleString()} columns
              </Badge>
              {previewMeta.truncatedRows || previewMeta.truncatedColumns ? (
                <Badge variant="outline" className="bg-background">
                  Preview truncated
                </Badge>
              ) : null}
            </div>
          ) : null}
          <div className="inline-flex items-center rounded-lg border border-border bg-muted/20 p-0.5">
            <Button
              size="sm"
              variant={source === "normalized" ? "secondary" : "ghost"}
              onClick={() => onSourceChange("normalized")}
              className="h-8 px-3 text-xs"
            >
              Normalized
            </Button>
            <Button
              size="sm"
              variant={source === "original" ? "secondary" : "ghost"}
              onClick={() => onSourceChange("original")}
              className="h-8 px-3 text-xs"
            >
              Original
            </Button>
          </div>
        </div>
      </div>

      {!canLoadSelectedSource ? (
        <div className="m-4 rounded-lg border border-border bg-background p-4 text-sm">
          <div className="font-medium text-foreground">Normalized preview unavailable</div>
          <div className="mt-1 text-muted-foreground">{normalizedState.reason}</div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => onSourceChange("original")}
          >
            Switch to original preview
          </Button>
        </div>
      ) : (
        <>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="min-h-0 flex-1 overflow-auto p-4">
              {hasSheetError || hasPreviewError ? (
                <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
                  Unable to load preview data. Refresh the page or try again later.
                </div>
              ) : isLoading ? (
                <div className="space-y-3">
                  {[0, 1, 2, 3].map((row) => (
                    <div key={row} className="flex gap-3">
                      <Skeleton className="h-6 w-12" />
                      <Skeleton className="h-6 w-24" />
                      <Skeleton className="h-6 w-24" />
                      <Skeleton className="h-6 w-24" />
                    </div>
                  ))}
                </div>
              ) : sheets.length === 0 ? (
                <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
                  No sheets available for this source.
                </div>
              ) : previewQuery.data ? (
                <div className="overflow-hidden rounded-lg border border-border bg-background">
                  <Table className="min-w-[720px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="sticky left-0 z-20 w-12 bg-muted/50 text-center">
                          #
                        </TableHead>
                        {columnLabels.map((label, index) => (
                          <TableHead
                            key={`${label}-${index}`}
                            className="min-w-24 bg-muted/30 text-center font-mono text-xs"
                          >
                            {label}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewRows.length === 0 ? (
                        <TableRow>
                          <TableCell
                            colSpan={Math.max(columnLabels.length + 1, 1)}
                            className="text-sm text-muted-foreground"
                          >
                            No rows available in the preview.
                          </TableCell>
                        </TableRow>
                      ) : (
                        previewRows.map((row, rowIndex) => {
                          const cells = Array.isArray(row) ? row : [];
                          return (
                            <TableRow key={`row-${rowIndex}`}>
                              <TableCell className="sticky left-0 z-10 w-12 bg-muted/40 text-center font-mono text-xs text-muted-foreground">
                                {rowIndex + 1}
                              </TableCell>
                              {columnLabels.map((_, colIndex) => (
                                <TableCell
                                  key={`cell-${rowIndex}-${colIndex}`}
                                  className={cn("max-w-64 truncate")}
                                  title={String(cells[colIndex] ?? "")}
                                >
                                  {cells[colIndex] ?? ""}
                                </TableCell>
                              ))}
                            </TableRow>
                          );
                        })
                      )}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
                  Select a sheet to view a preview.
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-border bg-background px-3 py-2">
            {sheets.length > 0 ? (
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {sheets.map((sheetOption) => {
                  const active = selectedSheet?.name === sheetOption.name;
                  return (
                    <button
                      key={`${sheetOption.index}:${sheetOption.name}`}
                      type="button"
                      className={cn(
                        "rounded-md border px-3 py-1.5 text-xs whitespace-nowrap",
                        active
                          ? "border-border bg-background text-foreground shadow-sm"
                          : "border-transparent text-muted-foreground hover:text-foreground",
                      )}
                      onClick={() => onSheetChange(sheetOption.name)}
                    >
                      {buildSheetLabel(sheetOption)}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">
                {sheetsQuery.isLoading ? "Loading sheets..." : "No sheets available."}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
