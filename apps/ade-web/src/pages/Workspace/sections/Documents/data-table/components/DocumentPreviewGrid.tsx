import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";

import { DataTable } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { DownloadIcon } from "@/components/icons";
import { cn } from "@/lib/utils";
import { resolveApiUrl } from "@api/client";
import { fetchRunColumns, fetchRunOutputPreview, fetchRunOutputSheets } from "@api/runs/api";
import { ApiError } from "@api/errors";
import { columnLabel } from "@pages/Workspace/sections/Documents/utils";

import type { DocumentListRow } from "../types";
import type { WorkbookSheetPreview } from "@pages/Workspace/sections/Documents/types";
import type { RunOutputSheet } from "@api/runs/api";

type PreviewRow = Record<string, string>;

const PREVIEW_MAX_ROWS = 200;
const PREVIEW_MAX_COLUMNS = 200;

interface DocumentPreviewGridProps {
  document: DocumentListRow;
}

export function DocumentPreviewGrid({
  document: doc,
}: DocumentPreviewGridProps) {
  const runId = doc.latestSuccessfulRun?.id ?? null;
  const normalizedDownloadUrl = runId
    ? resolveApiUrl(`/api/v1/runs/${runId}/output/download`)
    : null;
  const originalDownloadUrl = resolveApiUrl(
    `/api/v1/workspaces/${doc.workspaceId}/documents/${doc.id}/download`,
  );

  const sheetsQuery = useQuery({
    queryKey: ["run-output-sheets", runId],
    queryFn: ({ signal }) => fetchRunOutputSheets(runId ?? "", signal),
    staleTime: 30_000,
    enabled: Boolean(runId),
  });

  const sheets = sheetsQuery.data ?? [];
  const [selectedSheetIndex, setSelectedSheetIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!sheets.length) return;
    if (selectedSheetIndex !== null && sheets.some((sheet) => sheet.index === selectedSheetIndex)) {
      return;
    }
    const active = sheets.find((sheet) => sheet.is_active);
    setSelectedSheetIndex(active?.index ?? sheets[0].index);
  }, [sheets, selectedSheetIndex]);

  const activeSheetIndex = useMemo(() => {
    if (selectedSheetIndex !== null) return selectedSheetIndex;
    const active = sheets.find((sheet) => sheet.is_active);
    return active?.index ?? sheets[0]?.index ?? 0;
  }, [selectedSheetIndex, sheets]);

  const previewQuery = useQuery({
    queryKey: ["run-output-preview", runId, activeSheetIndex],
    queryFn: ({ signal }) =>
      fetchRunOutputPreview(
        runId ?? "",
        {
          maxRows: PREVIEW_MAX_ROWS,
          maxColumns: PREVIEW_MAX_COLUMNS,
          trimEmptyColumns: true,
          trimEmptyRows: true,
          sheetIndex: activeSheetIndex,
        },
        signal,
      ),
    staleTime: 30_000,
    enabled: Boolean(runId),
  });

  const columnsQuery = useQuery({
    queryKey: ["run-output-columns", runId, activeSheetIndex],
    queryFn: ({ signal }) =>
      fetchRunColumns(
        runId ?? "",
        { sheet_index: activeSheetIndex },
        signal,
      ),
    staleTime: 30_000,
    enabled: Boolean(runId),
  });

  const sheet = previewQuery.data ?? null;
  const mappingSummary = useMemo(() => {
    const columns = columnsQuery.data;
    if (!columns || !Array.isArray(columns)) {
      return null;
    }
    const totals = columns.reduce(
      (acc, column) => {
        if (column.mapping_status === "mapped") acc.mapped += 1;
        if (column.mapping_status === "unmapped") acc.unmapped += 1;
        return acc;
      },
      { mapped: 0, unmapped: 0 },
    );
    return totals;
  }, [columnsQuery.data]);
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

  const sheetMeta = sheet ? formatSheetMeta(sheet, mappingSummary) : null;
  const sheetTabs = sheets.length ? (
    <SheetTabs
      sheets={sheets}
      activeIndex={activeSheetIndex}
      onSelect={setSelectedSheetIndex}
    />
  ) : null;
  const downloadActions = (
    <>
      {normalizedDownloadUrl ? (
        <Button asChild variant="outline" size="sm" className="h-7 gap-1.5 px-2 text-xs">
          <a href={normalizedDownloadUrl} target="_blank" rel="noreferrer">
            <DownloadIcon className="h-3.5 w-3.5" />
            Normalized
          </a>
        </Button>
      ) : (
        <Button variant="outline" size="sm" className="h-7 gap-1.5 px-2 text-xs" disabled>
          <DownloadIcon className="h-3.5 w-3.5" />
          Normalized
        </Button>
      )}
      <Button asChild variant="outline" size="sm" className="h-7 gap-1.5 px-2 text-xs">
        <a href={originalDownloadUrl} target="_blank" rel="noreferrer">
          <DownloadIcon className="h-3.5 w-3.5" />
          Original
        </a>
      </Button>
    </>
  );

  if (!runId) {
    return (
    <PreviewShell actions={downloadActions} meta={sheetMeta}>
      <div className="text-xs text-muted-foreground">No successful run output available yet.</div>
    </PreviewShell>
    );
  }

  if (previewQuery.isLoading) {
    return (
    <PreviewShell actions={downloadActions} meta={sheetMeta}>
      <div className="text-xs text-muted-foreground">Loading preview...</div>
    </PreviewShell>
    );
  }

  if (previewQuery.isError) {
    const error = previewQuery.error;
    const message =
      error instanceof ApiError ? error.message : "Unable to load preview.";
    return (
      <PreviewShell actions={downloadActions} meta={sheetMeta}>
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
      <PreviewShell actions={downloadActions} meta={sheetMeta}>
        <div className="text-xs text-muted-foreground">No preview data available.</div>
      </PreviewShell>
    );
  }

  return (
    <PreviewShell actions={downloadActions} meta={sheetMeta}>
      <div className="flex flex-col gap-2">
        <DataTable
          table={table}
          showPagination={false}
          className="min-w-0 max-w-full gap-1.5 overflow-visible [&>div]:border-0 [&>div]:overflow-visible [&>div]:rounded-none [&_[data-slot=table-container]]:max-w-full [&_[data-slot=table-container]]:max-h-[min(360px,45vh)] [&_[data-slot=table-container]]:overflow-x-auto [&_[data-slot=table-container]]:overflow-y-auto [&_[data-slot=table]]:min-w-full [&_[data-slot=table]]:w-max [&_[data-slot=table]]:text-xs [&_[data-slot=table-head]]:!sticky [&_[data-slot=table-head]]:top-0 [&_[data-slot=table-head]]:!z-10 [&_[data-slot=table-head]]:h-8 [&_[data-slot=table-head]]:bg-muted/30 [&_[data-slot=table-head]]:text-[11px] [&_[data-slot=table-head]]:font-semibold [&_[data-slot=table-head]]:text-muted-foreground [&_[data-slot=table-head]]:truncate [&_[data-slot=table-head]]:backdrop-blur-sm [&_[data-slot=table-head]]:shadow-[inset_0_-1px_0_0_rgb(var(--sys-color-border))] [&_[data-slot=table-cell]]:px-2 [&_[data-slot=table-cell]]:py-1.5 [&_[data-slot=table-cell]]:text-xs [&_[data-slot=table-cell]]:truncate"
        />
        {sheetTabs}
      </div>
    </PreviewShell>
  );
}

function PreviewShell({
  title,
  actions,
  meta,
  children,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  meta?: string | null;
  children: ReactNode;
}) {
  const headerContent = actions ? (
    <div className="mt-1 flex flex-wrap items-center gap-2">{actions}</div>
  ) : title ? (
    <div className="truncate text-sm font-medium text-foreground">{title}</div>
  ) : null;

  return (
    <div className="flex w-full min-w-0 max-w-full flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm [contain:inline-size]">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border bg-muted/40 px-3 py-2">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Preview
          </div>
          {headerContent}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {meta ? <div className="text-xs text-muted-foreground">{meta}</div> : null}
        </div>
      </div>
      <div className="min-w-0 p-2">{children}</div>
    </div>
  );
}

function formatSheetMeta(
  sheet: WorkbookSheetPreview,
  mappingSummary: { mapped: number; unmapped: number } | null,
) {
  const parts = [sheet.name];
  if (mappingSummary) {
    parts.push(
      `${mappingSummary.mapped.toLocaleString()} matched columns`,
      `${mappingSummary.unmapped.toLocaleString()} unmatched columns`,
    );
  } else {
    parts.push(
      `${sheet.totalRows.toLocaleString()} rows`,
      `${sheet.totalColumns.toLocaleString()} columns`,
    );
  }

  if (sheet.truncatedRows || sheet.truncatedColumns) {
    const truncations: string[] = [];
    if (sheet.truncatedRows) truncations.push("rows truncated");
    if (sheet.truncatedColumns) truncations.push("columns truncated");
    parts.push(truncations.join(", "));
  }

  return parts.filter(Boolean).join(" | ");
}

function SheetTabs({
  sheets,
  activeIndex,
  onSelect,
}: {
  sheets: RunOutputSheet[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="flex w-full items-center gap-1 overflow-x-auto border-t border-border bg-muted/30 px-2 py-1">
      {sheets.map((sheet) => {
        const isActive = sheet.index === activeIndex;
        return (
          <button
            key={sheet.index}
            type="button"
            onClick={() => onSelect(sheet.index)}
            className={cn(
              "rounded-t-md border px-3 py-1 text-xs font-medium transition",
              isActive
                ? "border-border bg-background text-foreground shadow-sm"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50",
            )}
            aria-current={isActive ? "page" : undefined}
          >
            {sheet.name}
          </button>
        );
      })}
    </div>
  );
}
