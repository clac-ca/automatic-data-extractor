import { useCallback, useMemo } from "react";
import {
  DataEditor,
  GridCellKind,
  type GridColumn,
  type Item,
  type TextCell,
  type Theme,
} from "@glideapps/glide-data-grid";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const GRID_ROW_HEIGHT = 24;
const GRID_HEADER_HEIGHT = 28;
const GRID_ROW_MARKER_WIDTH = 44;

const COMPACT_GRID_THEME: Partial<Theme> = {
  baseFontStyle: "12px Inter, sans-serif",
  headerFontStyle: "600 11px Inter, sans-serif",
  editorFontSize: "12px",
  cellHorizontalPadding: 6,
  cellVerticalPadding: 2,
};

export function DocumentPreviewGrid({
  hasSheetError,
  hasPreviewError,
  isLoading,
  hasSheets,
  hasData,
  rows,
  columnLabels,
  className,
}: {
  hasSheetError: boolean;
  hasPreviewError: boolean;
  isLoading: boolean;
  hasSheets: boolean;
  hasData: boolean;
  rows: unknown[][];
  columnLabels: string[];
  className?: string;
}) {
  const gridRows = useMemo(() => {
    return rows.map((row) => (Array.isArray(row) ? row.map(renderPreviewCell) : []));
  }, [rows]);

  const columns = useMemo<readonly GridColumn[]>(() => {
    return columnLabels.map((label, columnIndex) => ({
      id: `column-${columnIndex}`,
      title: label,
      width: estimateColumnWidth(label, columnIndex, gridRows),
    }));
  }, [columnLabels, gridRows]);

  const getCellContent = useCallback(
    ([columnIndex, rowIndex]: Item): TextCell => {
      const value = gridRows[rowIndex]?.[columnIndex] ?? "";

      return {
        kind: GridCellKind.Text,
        data: value,
        displayData: value,
        allowOverlay: false,
        readonly: true,
      };
    },
    [gridRows],
  );

  if (hasSheetError || hasPreviewError) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        Unable to load preview data. Refresh the page or try again later.
      </div>
    );
  }

  if (isLoading) {
    return <LoadingState />;
  }

  if (!hasSheets) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        No sheets available for this source.
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        Select a sheet to view a preview.
      </div>
    );
  }

  if (gridRows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        No rows available in the preview.
      </div>
    );
  }

  return (
    <div className={cn("h-full overflow-hidden rounded-lg border border-border bg-background", className)}>
      <DataEditor
        width="100%"
        height="100%"
        columns={columns}
        rows={gridRows.length}
        getCellContent={getCellContent}
        getCellsForSelection={true}
        rowMarkers={{
          kind: "number",
          startIndex: 1,
          width: GRID_ROW_MARKER_WIDTH,
        }}
        rowHeight={GRID_ROW_HEIGHT}
        headerHeight={GRID_HEADER_HEIGHT}
        smoothScrollX
        smoothScrollY
        fixedShadowX
        fixedShadowY
        onPaste={false}
        theme={COMPACT_GRID_THEME}
      />
    </div>
  );
}

function LoadingState() {
  return (
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
  );
}

function estimateColumnWidth(label: string, columnIndex: number, rows: string[][]): number {
  const sampleSize = Math.min(rows.length, 40);
  let maxLength = label.length;

  for (let index = 0; index < sampleSize; index += 1) {
    const length = (rows[index]?.[columnIndex] ?? "").length;
    if (length > maxLength) {
      maxLength = length;
    }
  }

  const estimated = maxLength * 7 + 24;
  return clamp(estimated, 72, 220);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function renderPreviewCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (
    typeof value === "number"
    || typeof value === "boolean"
    || typeof value === "bigint"
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
