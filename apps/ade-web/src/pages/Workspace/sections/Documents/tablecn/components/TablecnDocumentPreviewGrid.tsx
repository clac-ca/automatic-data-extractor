import { useMemo, type ReactNode } from "react";
import { getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";

import { DataTable } from "@components/tablecn/data-table/data-table";
import { Button } from "@components/tablecn/ui/button";
import { apiFetch } from "@api/client";
import { ApiError, tryParseProblemDetails } from "@api/errors";
import { columnLabel } from "@pages/Workspace/sections/Documents/utils";

import type { DocumentListRow } from "../types";
import type { WorkbookPreview, WorkbookSheet } from "@pages/Workspace/sections/Documents/types";

type PreviewRow = Record<string, string>;

const PREVIEW_MAX_ROWS = 200;

async function fetchDocumentPreview(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<WorkbookPreview> {
  const params = new URLSearchParams({
    maxRows: String(PREVIEW_MAX_ROWS),
    trimEmptyColumns: "true",
    trimEmptyRows: "true",
  });
  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}/preview?${params.toString()}`,
    { signal },
  );
  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = problem?.title ?? `Preview request failed (${response.status})`;
    throw new ApiError(message, response.status, problem);
  }
  return (await response.json()) as WorkbookPreview;
}

interface TablecnDocumentPreviewGridProps {
  document: DocumentListRow;
}

export function TablecnDocumentPreviewGrid({
  document: doc,
}: TablecnDocumentPreviewGridProps) {
  const previewQuery = useQuery({
    queryKey: ["tablecn-document-preview", doc.workspaceId, doc.id],
    queryFn: ({ signal }) => fetchDocumentPreview(doc.workspaceId, doc.id, signal),
    staleTime: 30_000,
    enabled: Boolean(doc.workspaceId && doc.id),
  });

  const sheet = previewQuery.data?.sheets?.[0] ?? null;
  const columnCount = useMemo(() => {
    if (!sheet) return 0;
    const maxRowLength = sheet.rows.reduce(
      (max, row) => Math.max(max, row.length),
      0,
    );
    return Math.max(sheet.headers.length, maxRowLength);
  }, [sheet]);
  const columnIds = useMemo(
    () => Array.from({ length: columnCount }, (_, index) => `col_${index}`),
    [columnCount],
  );

  const columns = useMemo<ColumnDef<PreviewRow>[]>(() => {
    if (!sheet) return [];
    return columnIds.map((id, index) => {
      const header = sheet.headers[index] ?? "";
      const label = header.trim() || columnLabel(index);
      return {
        id,
        accessorKey: id,
        header: label,
        cell: ({ getValue }) => {
          const value = getValue<string>() ?? "";
          return (
            <div className="w-full truncate" title={value}>
              {value}
            </div>
          );
        },
      };
    });
  }, [columnIds, sheet]);

  const data = useMemo(() => {
    if (!sheet) return [];
    return sheet.rows.map((row) => {
      const record: PreviewRow = {};
      for (let index = 0; index < columnCount; index += 1) {
        record[columnIds[index]] = row[index] ?? "";
      }
      return record;
    });
  }, [columnCount, columnIds, sheet]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    defaultColumn: {
      size: 140,
      minSize: 100,
      maxSize: 240,
    },
  });

  if (previewQuery.isLoading) {
    return (
      <PreviewShell title={doc.name}>
        <div className="text-xs text-muted-foreground">Loading preview...</div>
      </PreviewShell>
    );
  }

  if (previewQuery.isError) {
    const error = previewQuery.error;
    const message =
      error instanceof ApiError ? error.message : "Unable to load preview.";
    return (
      <PreviewShell title={doc.name}>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>{message}</span>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => previewQuery.refetch()}
          >
            Try again
          </Button>
        </div>
      </PreviewShell>
    );
  }

  if (!sheet) {
    return (
      <PreviewShell title={doc.name}>
        <div className="text-xs text-muted-foreground">No preview data available.</div>
      </PreviewShell>
    );
  }

  const sheetMeta = formatSheetMeta(sheet, previewQuery.data?.sheets?.length ?? 0);

  return (
    <PreviewShell title={doc.name} meta={sheetMeta}>
      <DataTable
        table={table}
        showPagination={false}
        className="min-w-0 max-w-full gap-1.5 overflow-visible [&>div]:border-0 [&>div]:overflow-visible [&>div]:rounded-none [&_[data-slot=table-container]]:max-w-full [&_[data-slot=table-container]]:max-h-[min(360px,45vh)] [&_[data-slot=table-container]]:overflow-x-auto [&_[data-slot=table-container]]:overflow-y-auto [&_[data-slot=table]]:min-w-full [&_[data-slot=table]]:w-max [&_[data-slot=table]]:text-xs [&_[data-slot=table-head]]:!sticky [&_[data-slot=table-head]]:top-0 [&_[data-slot=table-head]]:!z-10 [&_[data-slot=table-head]]:h-8 [&_[data-slot=table-head]]:bg-muted/30 [&_[data-slot=table-head]]:text-[11px] [&_[data-slot=table-head]]:font-semibold [&_[data-slot=table-head]]:text-muted-foreground [&_[data-slot=table-head]]:truncate [&_[data-slot=table-head]]:backdrop-blur-sm [&_[data-slot=table-head]]:shadow-[inset_0_-1px_0_0_rgb(var(--sys-color-border))] [&_[data-slot=table-cell]]:px-2 [&_[data-slot=table-cell]]:py-1.5 [&_[data-slot=table-cell]]:text-xs [&_[data-slot=table-cell]]:truncate"
      />
    </PreviewShell>
  );
}

function PreviewShell({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="flex w-full min-w-0 max-w-full flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm [contain:inline-size]">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border bg-muted/40 px-3 py-2">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Preview
          </div>
          <div className="truncate text-sm font-medium text-foreground">
            {title}
          </div>
        </div>
        {meta ? <div className="text-xs text-muted-foreground">{meta}</div> : null}
      </div>
      <div className="min-w-0 p-2">{children}</div>
    </div>
  );
}

function formatSheetMeta(sheet: WorkbookSheet, sheetCount: number) {
  const parts = [
    sheet.name,
    `${sheet.totalRows.toLocaleString()} rows`,
    `${sheet.totalColumns.toLocaleString()} columns`,
  ];

  if (sheet.truncatedRows || sheet.truncatedColumns) {
    const truncations: string[] = [];
    if (sheet.truncatedRows) truncations.push("rows truncated");
    if (sheet.truncatedColumns) truncations.push("columns truncated");
    parts.push(truncations.join(", "));
  }

  if (sheetCount > 1) {
    parts.push(`1 of ${sheetCount} sheets`);
  }

  return parts.filter(Boolean).join(" | ");
}
