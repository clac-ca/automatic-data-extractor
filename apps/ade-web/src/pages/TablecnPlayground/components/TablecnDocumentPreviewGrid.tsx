import { useMemo } from "react";
import { getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";

import { DataTable } from "@components/tablecn/data-table/data-table";
import { apiFetch } from "@api/client";
import { ApiError } from "@api/errors";
import { Button } from "@components/ui/button";
import { columnLabel } from "@pages/Workspace/sections/Documents/utils";

import type { DocumentListRow } from "../types";
import type { WorkbookPreview, WorkbookSheet } from "@pages/Workspace/sections/Documents/types";

type PreviewRow = Record<string, string>;

const PREVIEW_MAX_ROWS = 200;
const PREVIEW_MAX_COLUMNS = 50;

async function fetchDocumentPreview(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<WorkbookPreview> {
  const params = new URLSearchParams({
    maxRows: String(PREVIEW_MAX_ROWS),
    maxColumns: String(PREVIEW_MAX_COLUMNS),
  });
  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}/preview?${params.toString()}`,
    { signal },
  );
  if (!response.ok) {
    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Preview request failed (${response.status})`;
    throw new ApiError(message, response.status, problem);
  }
  return (await response.json()) as WorkbookPreview;
}

async function tryParseProblem(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return (await response.clone().json()) as {
      title?: string;
      detail?: string;
      status?: number;
    };
  } catch {
    return undefined;
  }
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
    const requestedCount = Math.max(sheet.headers.length, maxRowLength);
    return Math.min(PREVIEW_MAX_COLUMNS, requestedCount);
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
      <div className="p-3 text-sm text-muted-foreground">
        Loading preview...
      </div>
    );
  }

  if (previewQuery.isError) {
    const error = previewQuery.error;
    const message =
      error instanceof ApiError ? error.message : "Unable to load preview.";
    return (
      <div className="flex flex-wrap items-center gap-3 p-3 text-sm text-muted-foreground">
        <span>{message}</span>
        <Button variant="secondary" size="sm" onClick={() => previewQuery.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  if (!sheet) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        No preview data available.
      </div>
    );
  }

  const sheetMeta = formatSheetMeta(sheet, previewQuery.data?.sheets?.length ?? 0);

  return (
    <div className="flex min-w-0 flex-col gap-2 p-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>Previewing {doc.name}</span>
        {sheetMeta ? <span>{sheetMeta}</span> : null}
      </div>
      <DataTable
        table={table}
        showPagination={false}
        className="max-w-full min-w-0 [&_[data-slot=table-container]]:max-w-full [&_[data-slot=table-container]]:overflow-x-auto [&_[data-slot=table]]:min-w-full [&_[data-slot=table]]:w-max [&_[data-slot=table-cell]]:truncate [&_[data-slot=table-head]]:truncate"
      />
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
