import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchDocumentPreview,
  fetchDocumentSheets,
  type DocumentSheet,
} from "@/api/documents";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { columnLabel } from "@/pages/Workspace/sections/Documents/shared/utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

const DEFAULT_MAX_ROWS = 200;
const DEFAULT_MAX_COLUMNS = 50;

function pickDefaultSheet(sheets: DocumentSheet[]) {
  if (sheets.length === 0) return null;
  return sheets.find((sheet) => sheet.is_active) ?? sheets[0];
}

function buildSheetLabel(sheet: DocumentSheet) {
  return sheet.name || `Sheet ${sheet.index + 1}`;
}

export function DocumentsPreviewContent({
  workspaceId,
  document,
}: {
  workspaceId: string;
  document: DocumentRow;
}) {
  const sheetsQuery = useQuery({
    queryKey: ["document-sheets", workspaceId, document.id],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, document.id, signal),
    enabled: Boolean(workspaceId && document.id),
    staleTime: 30_000,
  });

  const sheets = sheetsQuery.data ?? [];
  const defaultSheet = useMemo(() => pickDefaultSheet(sheets), [sheets]);
  const [activeSheetId, setActiveSheetId] = useState<string | null>(null);

  useEffect(() => {
    if (!sheets.length) {
      setActiveSheetId(null);
      return;
    }

    const fallback = defaultSheet ? String(defaultSheet.index) : String(sheets[0]?.index ?? 0);
    if (!activeSheetId) {
      setActiveSheetId(fallback);
      return;
    }

    if (!sheets.some((sheet) => String(sheet.index) === activeSheetId)) {
      setActiveSheetId(fallback);
    }
  }, [activeSheetId, defaultSheet, sheets]);

  const activeSheet =
    sheets.find((sheet) => String(sheet.index) === activeSheetId) ?? defaultSheet ?? null;

  const previewQuery = useQuery({
    queryKey: [
      "document-preview",
      workspaceId,
      document.id,
      activeSheet?.index ?? null,
      DEFAULT_MAX_ROWS,
      DEFAULT_MAX_COLUMNS,
    ],
    queryFn: ({ signal }) =>
      fetchDocumentPreview(
        workspaceId,
        document.id,
        {
          maxRows: DEFAULT_MAX_ROWS,
          maxColumns: DEFAULT_MAX_COLUMNS,
          sheetIndex: activeSheet?.index ?? undefined,
        },
        signal,
      ),
    enabled: Boolean(workspaceId && document.id && activeSheet),
    staleTime: 30_000,
  });

  const headerLabels = useMemo(() => {
    if (!previewQuery.data) return [];
    return previewQuery.data.headers.map((header, index) =>
      header?.trim() ? header : columnLabel(index),
    );
  }, [previewQuery.data]);

  const previewMeta = useMemo(() => {
    if (!previewQuery.data) return null;
    const { totalRows, totalColumns, truncatedRows, truncatedColumns } = previewQuery.data;
    return {
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns,
    };
  }, [previewQuery.data]);

  const hasSheetError = sheetsQuery.isError;
  const hasPreviewError = previewQuery.isError;
  const isLoadingPreview = previewQuery.isLoading || sheetsQuery.isLoading;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background px-4 py-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Data preview</div>
          <div className="text-xs text-muted-foreground">
            {document.name}
          </div>
        </div>
        {previewMeta ? (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline" className="bg-background">
              {previewMeta.totalRows.toLocaleString()} rows
            </Badge>
            <Badge variant="outline" className="bg-background">
              {previewMeta.totalColumns.toLocaleString()} columns
            </Badge>
            {(previewMeta.truncatedRows || previewMeta.truncatedColumns) ? (
              <Badge variant="outline" className="bg-background">
                Preview truncated
              </Badge>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="flex items-center gap-2 border-b border-border bg-muted/20 px-4 py-2">
        {sheets.length > 0 ? (
          <TabsRoot value={activeSheetId ?? ""} onValueChange={setActiveSheetId}>
            <TabsList className="flex flex-wrap gap-2 bg-transparent p-0">
              {sheets.map((sheet) => (
                <TabsTrigger
                  key={sheet.index}
                  value={String(sheet.index)}
                  className={cn(
                    "rounded-md border border-transparent px-3 py-1 text-xs",
                    activeSheet?.index === sheet.index
                      ? "border-border bg-background text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {buildSheetLabel(sheet)}
                </TabsTrigger>
              ))}
            </TabsList>
          </TabsRoot>
        ) : (
          <div className="text-xs text-muted-foreground">
            {sheetsQuery.isLoading ? "Loading sheets…" : "No sheets available."}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto bg-background">
        {hasSheetError || hasPreviewError ? (
          <div className="m-4 rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            Unable to load preview data. Refresh the page or try again later.
          </div>
        ) : isLoadingPreview ? (
          <div className="space-y-3 p-4">
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="flex gap-3">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-6 w-24" />
              </div>
            ))}
          </div>
        ) : previewQuery.data ? (
          <div className="p-4">
            <Table className="min-w-[720px]">
              <TableHeader>
                <TableRow>
                  {headerLabels.map((label, index) => (
                    <TableHead key={`${label}-${index}`}>{label}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewQuery.data.rows.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={Math.max(headerLabels.length, 1)}
                      className="text-sm text-muted-foreground"
                    >
                      No rows available in the preview.
                    </TableCell>
                  </TableRow>
                ) : (
                  previewQuery.data.rows.map((row, rowIndex) => (
                    <TableRow key={`row-${rowIndex}`}>
                      {headerLabels.map((_, colIndex) => (
                        <TableCell key={`cell-${rowIndex}-${colIndex}`}>
                          {row[colIndex] ?? ""}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="m-4 rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            Select a sheet to view a preview.
          </div>
        )}
      </div>
    </div>
  );
}
