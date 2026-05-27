import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DataEditor,
  GridCellKind,
  getLuminance,
  textCellRenderer,
  type EditableGridCell,
  type GridColumn,
  type InnerGridCell,
  type InternalCellRenderer,
  type Item,
  type TextCell,
  type Theme,
} from "@glideapps/glide-data-grid";

import { useGlideDataEditorTheme } from "@/providers/theme/glideTheme";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

import type { PreviewCellFormat } from "../model";

const GRID_ROW_HEIGHT = 24;
const GRID_HEADER_HEIGHT = 28;
const GRID_ROW_MARKER_WIDTH = 46;
const ROW_NUMBER_COLUMN_ID = "__row-number";
const MIN_VISIBLE_COLUMNS = 26;
const MIN_VISIBLE_ROWS = 50;

const SPREADSHEET_PREVIEW_THEME: Partial<Theme> = {
  baseFontStyle: "12px Inter, sans-serif",
  headerFontStyle: "600 11px Inter, sans-serif",
  editorFontSize: "12px",
  cellHorizontalPadding: 8,
  cellVerticalPadding: 2,
  bgCellMedium: "#f8f9fa",
  bgHeader: "#f1f3f4",
  bgHeaderHovered: "#e8eaed",
  bgHeaderHasFocus: "#dfe3ea",
  borderColor: "#d8dde6",
  horizontalBorderColor: "#e5e8ee",
  textHeader: "#3c4043",
};

const PREVIEW_TEXT_CELL_RENDERER: InternalCellRenderer<TextCell> = {
  ...textCellRenderer,
  draw: (args, cell) => {
    const bgCell = cell.themeOverride?.bgCell;
    const textColor = cell.themeOverride?.textDark;

    if (bgCell) {
      // 1. Draw custom background color
      args.ctx.fillStyle = bgCell;
      args.ctx.fillRect(args.rect.x, args.rect.y, args.rect.width, args.rect.height);

      // 2. Draw selection overlay if highlighted
      if (args.highlighted) {
        args.ctx.save();
        args.ctx.fillStyle = args.theme.accentLight;
        args.ctx.globalAlpha = 0.25; // Draw overlay with opacity to preserve the original color underneath
        args.ctx.fillRect(args.rect.x, args.rect.y, args.rect.width, args.rect.height);
        args.ctx.restore();
      }

      // 3. Draw text with custom textDark and transparent fill color to prevent overwrite
      const strokeColor = textColor || args.theme.textDark;
      args.ctx.fillStyle = strokeColor; // Make sure the canvas font color brush is set back to our text color instead of selection color
      textCellRenderer.draw(
        {
          ...args,
          cellFillColor: "rgba(0,0,0,0)",
          theme: {
            ...args.theme,
            textDark: strokeColor,
          },
        },
        cell,
      );
      return;
    }

    // Default cell highlight contrast rendering
    if (!args.highlighted || !textColor) {
      textCellRenderer.draw(args, cell);
      return;
    }

    const contrastTextColor = getContrastTextColor(args.cellFillColor);
    if (!contrastTextColor || contrastTextColor.toLowerCase() === textColor.toLowerCase()) {
      textCellRenderer.draw(args, cell);
      return;
    }

    textCellRenderer.draw(
      {
        ...args,
        theme: {
          ...args.theme,
          textDark: contrastTextColor,
        },
      },
      cell,
    );
  },
};
const PREVIEW_CELL_RENDERERS = [PREVIEW_TEXT_CELL_RENDERER] as unknown as readonly InternalCellRenderer<InnerGridCell>[];

export function DocumentPreviewGrid({
  hasSheetError,
  hasPreviewError,
  isLoading,
  hasSheets,
  hasData,
  rows,
  rowNumbers,
  columnLabels,
  cellFormats,
  isReadOnly = false,
  onRowsChange,
  onHeaderMenuClick,
  className,
}: {
  hasSheetError: boolean;
  hasPreviewError: boolean;
  isLoading: boolean;
  hasSheets: boolean;
  hasData: boolean;
  rows: unknown[][];
  rowNumbers: number[];
  columnLabels: string[];
  cellFormats: PreviewCellFormat[];
  isReadOnly?: boolean;
  onRowsChange?: (rows: string[][]) => void;
  onHeaderMenuClick?: (columnIndex: number) => void;
  className?: string;
}) {
  const paletteTheme = useGlideDataEditorTheme();

  const dataEditorTheme = useMemo(
    () => ({
      ...paletteTheme,
      ...SPREADSHEET_PREVIEW_THEME,
      fgIconHeader: paletteTheme.accentColor || "#4f5dff",
      bgIconHeader: "rgba(0,0,0,0)",
    }),
    [paletteTheme],
  );

  const customHeaderIcons = useMemo(() => {
    return {
      plus: (props: { fgColor: string }) => `
        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none">
          <!-- Background thick stroke for high-contrast halo on dark selected headers -->
          <path d="M5 12h14" stroke="#ffffff" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M12 5v14" stroke="#ffffff" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round" />
          <!-- Foreground stroke in brand accent color -->
          <path d="M5 12h14" stroke="${props.fgColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M12 5v14" stroke="${props.fgColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      `
    };
  }, []);

  const initialGridRows = useMemo(() => {
    return rows.map((row) => (Array.isArray(row) ? row.map(renderPreviewCell) : []));
  }, [rows]);

  const [gridRows, setGridRows] = useState<string[][]>(initialGridRows);

  useEffect(() => {
    setGridRows(initialGridRows);
  }, [initialGridRows]);

  const renderedColumnLabels = useMemo(() => {
    if (columnLabels.length >= MIN_VISIBLE_COLUMNS) {
      return columnLabels;
    }

    const labels = [...columnLabels];
    for (let index = columnLabels.length; index < MIN_VISIBLE_COLUMNS; index += 1) {
      labels.push(spreadsheetColumnLabel(index));
    }
    return labels;
  }, [columnLabels]);

  const rowCount = Math.max(gridRows.length, MIN_VISIBLE_ROWS);

  const cellFormatByPosition = useMemo(() => {
    return new Map(cellFormats.map((format) => [`${format.row}:${format.column}`, format]));
  }, [cellFormats]);

  const columns = useMemo<readonly GridColumn[]>(() => {
    return [
      {
        id: ROW_NUMBER_COLUMN_ID,
        title: "",
        width: GRID_ROW_MARKER_WIDTH,
        themeOverride: {
          bgCell: "#f1f3f4",
          textDark: "#5f6368",
        },
      },
      ...renderedColumnLabels.map((label, columnIndex) => ({
        id: `column-${columnIndex}`,
        title: label,
        hasMenu: true,
        menuIcon: "plus",
        width: estimateColumnWidth(label, columnIndex, gridRows),
      })),
    ];
  }, [gridRows, renderedColumnLabels]);

  const getCellContent = useCallback(
    ([columnIndex, rowIndex]: Item): TextCell => {
      if (columnIndex === 0) {
        const value = String(resolveRowNumber(rowNumbers, rowIndex));
        return {
          kind: GridCellKind.Text,
          data: value,
          displayData: value,
          allowOverlay: false,
          readonly: true,
          contentAlign: "center",
          themeOverride: {
            bgCell: "#f1f3f4",
            textDark: "#5f6368",
          },
        };
      }

      const dataColumnIndex = columnIndex - 1;
      const value = gridRows[rowIndex]?.[dataColumnIndex] ?? "";
      const cellFormat = cellFormatByPosition.get(`${rowIndex}:${dataColumnIndex}`);

      return {
        kind: GridCellKind.Text,
        data: value,
        displayData: value,
        allowOverlay: true,
        readonly: isReadOnly,
        ...buildCellFormatProps(cellFormat),
      };
    },
    [cellFormatByPosition, gridRows, rowNumbers, isReadOnly],
  );

  const handleCellEdited = useCallback((cell: Item, newValue: EditableGridCell) => {
    if (isReadOnly) {
      return;
    }
    const [columnIndex, rowIndex] = cell;
    if (columnIndex === 0 || newValue.kind !== GridCellKind.Text) {
      return;
    }

    const dataColumnIndex = columnIndex - 1;
    setGridRows((currentRows) => {
      const nextRows = currentRows.map((row) => [...row]);
      while (nextRows.length <= rowIndex) {
        nextRows.push([]);
      }
      const nextRow = nextRows[rowIndex];
      while (nextRow.length <= dataColumnIndex) {
        nextRow.push("");
      }
      nextRow[dataColumnIndex] = newValue.data;

      if (onRowsChange) {
        onRowsChange(nextRows);
      }

      return nextRows;
    });
  }, [isReadOnly, onRowsChange]);

  const handleHeaderMenuClick = useCallback(
    (col: number) => {
      if (col > 0 && onHeaderMenuClick) {
        onHeaderMenuClick(col - 1);
      }
    },
    [onHeaderMenuClick],
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
        rows={rowCount}
        getCellContent={getCellContent}
        getCellsForSelection={true}
        freezeColumns={1}
        rangeSelect="multi-rect"
        rowSelect="none"
        columnSelect="multi"
        drawFocusRing
        scrollToActiveCell
        cellActivationBehavior="double-click"
        rowHeight={GRID_ROW_HEIGHT}
        headerHeight={GRID_HEADER_HEIGHT}
        smoothScrollX
        smoothScrollY
        fixedShadowX
        fixedShadowY
        onCellEdited={handleCellEdited}
        onHeaderMenuClick={handleHeaderMenuClick}
        onHeaderClick={handleHeaderMenuClick}
        onPaste={true}
        editOnType
        copyHeaders={false}
        renderers={PREVIEW_CELL_RENDERERS}
        theme={dataEditorTheme}
        headerIcons={customHeaderIcons}
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
  return clamp(estimated, 72, 260);
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

function resolveRowNumber(rowNumbers: number[], rowIndex: number): number {
  const rowNumber = rowNumbers[rowIndex];
  if (typeof rowNumber === "number") {
    return rowNumber;
  }

  const lastRowNumber = rowNumbers.at(-1) ?? 0;
  return lastRowNumber + (rowIndex - rowNumbers.length) + 1;
}

function buildCellFormatProps(format: PreviewCellFormat | undefined): Partial<TextCell> {
  if (!format) {
    return {};
  }

  const themeOverride: NonNullable<TextCell["themeOverride"]> = {};
  if (format.bgColor) {
    themeOverride.bgCell = format.bgColor;
  }
  if (format.textColor) {
    themeOverride.textDark = format.textColor;
  }
  const fontStyle = buildFontStyle(format);
  if (fontStyle) {
    themeOverride.baseFontStyle = fontStyle;
  }

  return {
    allowWrapping: format.wrapText === true,
    contentAlign: normalizeHorizontalAlign(format.horizontalAlign),
    themeOverride: Object.keys(themeOverride).length > 0 ? themeOverride : undefined,
  };
}

function normalizeHorizontalAlign(value: string | null | undefined): TextCell["contentAlign"] {
  if (value === "center" || value === "right") {
    return value;
  }
  return "left";
}

function buildFontStyle(format: PreviewCellFormat): string | undefined {
  if (!format.bold && !format.italic) {
    return undefined;
  }

  const style = format.italic ? "italic" : "normal";
  const weight = format.bold ? "700" : "400";
  return `${style} ${weight} 12px Inter, sans-serif`;
}

function getContrastTextColor(backgroundColor: string): string | null {
  try {
    return getLuminance(backgroundColor) > 0.58 ? "#111827" : "#ffffff";
  } catch {
    return null;
  }
}

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
