import * as React from "react";
import {
  DataEditor,
  GridCellKind,
  type GridCell,
  type GridColumn,
  type Item,
} from "@glideapps/glide-data-grid";

import { columnLabel } from "../../utils";

type DocumentsPreviewGridProps = {
  headerRow: string[];
  rows: string[][];
  columnCount: number;
  resetKey: string;
};

export function DocumentsPreviewGrid({
  headerRow,
  rows,
  columnCount,
}: DocumentsPreviewGridProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = React.useState(() => ({
    width: 0,
    height: 0,
  }));

  React.useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setContainerSize({
        width: Math.floor(width),
        height: Math.floor(height),
      });
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const columns = React.useMemo<GridColumn[]>(() => {
    if (!columnCount) return [];

    return Array.from({ length: columnCount }, (_, index) => {
      const header = headerRow[index] ?? "";
      const title = header.trim() ? header : columnLabel(index);

      return {
        title,
        id: `col_${index}`,
        width: 160,
      };
    });
  }, [columnCount, headerRow]);

  const getCellContent = React.useCallback(
    (cell: Item): GridCell => {
      const [col, row] = cell;
      const value = rows[row]?.[col] ?? "";

      return {
        kind: GridCellKind.Text,
        allowOverlay: true,
        readonly: true,
        displayData: value,
        data: value,
      };
    },
    [rows],
  );

  const width = containerSize.width || 800;
  const height = containerSize.height || 500;

  return (
    <div
      ref={containerRef}
      className="min-h-0 flex-1 overflow-hidden rounded-md border"
    >
      <DataEditor
        columns={columns}
        rows={rows.length}
        getCellContent={getCellContent}
        width={width}
        height={height}
      />
    </div>
  );
}
