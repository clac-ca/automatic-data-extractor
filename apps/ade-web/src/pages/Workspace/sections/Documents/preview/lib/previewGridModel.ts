export type PreviewGridModel = {
  headerRow: string[];
  bodyRows: string[][];
  columnCount: number;
};

export function buildPreviewGridModel(rows: string[][]): PreviewGridModel {
  if (!rows.length) {
    return { headerRow: [], bodyRows: [], columnCount: 0 };
  }

  const headerRow = rows[0] ?? [];
  const bodyRows = rows.length > 1 ? rows.slice(1) : [];
  const columnCount = rows.reduce((max, row) => Math.max(max, row.length), 0);

  return { headerRow, bodyRows, columnCount };
}
