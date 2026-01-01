import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";

import { DataGrid } from "@components/tablecn/data-grid/data-grid";
import { useDataGrid } from "@components/tablecn/hooks/use-data-grid";
import { apiFetch } from "@api/client";
import { ApiError } from "@api/errors";
import { Button } from "@components/ui/button";

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
  });

  const sheet = previewQuery.data?.sheets?.[0] ?? null;
  const columnIds = useMemo(
    () => (sheet ? sheet.headers.map((_, index) => `col_${index}`) : []),
    [sheet],
  );

  const columns = useMemo<ColumnDef<PreviewRow>[]>(() => {
    if (!sheet) return [];
    return sheet.headers.map((header, index) => {
      const id = columnIds[index] ?? `col_${index}`;
      const label = header?.trim() || `Column ${index + 1}`;
      return {
        id,
        accessorKey: id,
        header: label,
        minSize: 120,
        meta: {
          label,
          cell: { variant: "short-text" },
        },
      };
    });
  }, [columnIds, sheet]);

  const data = useMemo(() => {
    if (!sheet) return [];
    return sheet.rows.map((row) => {
      const record: PreviewRow = {};
      columnIds.forEach((columnId, index) => {
        record[columnId] = row[index] ?? "";
      });
      return record;
    });
  }, [columnIds, sheet]);

  const { table, ...dataGridProps } = useDataGrid({
    data,
    columns,
    readOnly: true,
    enableSearch: false,
    enablePaste: false,
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
    <div className="flex flex-col gap-3 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>Previewing {doc.name}</span>
        {sheetMeta ? <span>{sheetMeta}</span> : null}
      </div>
      <DataGrid
        {...dataGridProps}
        table={table}
        height={260}
        stretchColumns
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
