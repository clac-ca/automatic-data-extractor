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
import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { getNormalizedPreviewState } from "../state";
import { buildPreviewCountSummary, type PreviewCellFormat, type PreviewDisplayPreferences } from "../model";

const DEFAULT_MAX_ROWS = 10_000;
const DEFAULT_MAX_COLUMNS = 10_000;

export type PreviewSheet = {
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
  if (sheets.length === 0) {
    return null;
  }

  return sheets.find((sheet) => sheet.is_active) ?? sheets[0];
}

export function useDocumentPreviewModel({
  workspaceId,
  document,
  source,
  sheet,
  onSheetChange,
  displayPreferences,
}: {
  workspaceId: string;
  document: DocumentRow;
  source: DocumentPreviewSource;
  sheet: string | null;
  onSheetChange: (sheet: string | null) => void;
  displayPreferences: PreviewDisplayPreferences;
}) {
  const normalizedState = getNormalizedPreviewState(document);
  const normalizedRunId = normalizedState.available ? document.lastRun?.id ?? null : null;
  const canLoadSelectedSource = source === "original" || Boolean(normalizedRunId);

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
        : fetchRunOutputSheets(workspaceId, normalizedRunId as string, signal),
    enabled: Boolean(workspaceId && document.id && canLoadSelectedSource),
    staleTime: 30_000,
  });

  const sheets = sheetsQuery.data ?? [];

  const selectedSheet = useMemo(() => {
    if (sheets.length === 0) {
      return null;
    }

    if (sheet) {
      const selectedByName = sheets.find((entry) => entry.name === sheet);
      if (selectedByName) {
        return selectedByName;
      }
    }

    return pickDefaultSheet(sheets);
  }, [sheet, sheets]);

  useEffect(() => {
    if (!canLoadSelectedSource) {
      return;
    }

    if (sheets.length === 0) {
      if (sheet) {
        onSheetChange(null);
      }
      return;
    }

    const nextSheet = selectedSheet?.name ?? null;
    if (sheet !== nextSheet) {
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
      displayPreferences.trimEmptyRows,
      displayPreferences.trimEmptyColumns,
    ],
    queryFn: ({ signal }) => {
      const options = {
        maxRows: DEFAULT_MAX_ROWS,
        maxColumns: DEFAULT_MAX_COLUMNS,
        trimEmptyRows: displayPreferences.trimEmptyRows,
        trimEmptyColumns: displayPreferences.trimEmptyColumns,
        sheetIndex: selectedSheet?.index ?? undefined,
      };

      if (source === "original") {
        return fetchDocumentPreview(workspaceId, document.id, options, signal);
      }

      return fetchRunOutputPreview(workspaceId, normalizedRunId as string, options, signal);
    },
    enabled: Boolean(workspaceId && document.id && canLoadSelectedSource && selectedSheet),
    staleTime: 30_000,
  });

  const hiddenColumns = useMemo(() => {
    return new Set(previewQuery.data?.hiddenColumns ?? []);
  }, [previewQuery.data?.hiddenColumns]);

  const hiddenRows = useMemo(() => {
    return new Set(previewQuery.data?.hiddenRows ?? []);
  }, [previewQuery.data?.hiddenRows]);

  const rawRows = useMemo(() => previewQuery.data?.rows ?? [], [previewQuery.data]);

  const rawColumnCount = useMemo(
    () => rawRows.reduce((max, row) => Math.max(max, row.length), 0),
    [rawRows],
  );

  const visibleIndices = useMemo(() => {
    const totalColumnCount =
      typeof previewQuery.data?.totalColumns === "number"
        ? previewQuery.data.totalColumns
        : rawColumnCount;
    const renderedColumnCount = displayPreferences.trimEmptyColumns ? rawColumnCount : totalColumnCount;

    const indices: number[] = [];
    for (let index = 0; index < renderedColumnCount; index += 1) {
      if (displayPreferences.showHiddenRowsAndColumns || !hiddenColumns.has(index)) {
        indices.push(index);
      }
    }
    return indices;
  }, [
    displayPreferences.showHiddenRowsAndColumns,
    displayPreferences.trimEmptyColumns,
    previewQuery.data?.totalColumns,
    rawColumnCount,
    hiddenColumns,
  ]);

  const previewRows = useMemo(() => {
    const visibleRows = displayPreferences.showHiddenRowsAndColumns
      ? rawRows.map((row, index) => ({ row, originalIndex: index }))
      : rawRows
        .map((row, index) => ({ row, originalIndex: index }))
        .filter(({ originalIndex }) => !hiddenRows.has(originalIndex));

    if (displayPreferences.showHiddenRowsAndColumns && hiddenColumns.size === 0) {
      return visibleRows.map(({ row }) => row);
    }
    return visibleRows.map(({ row }) => visibleIndices.map((index) => row[index] ?? ""));
  }, [
    displayPreferences.showHiddenRowsAndColumns,
    rawRows,
    visibleIndices,
    hiddenColumns.size,
    hiddenRows,
  ]);

  const rowNumbers = useMemo(() => {
    const visibleRows = displayPreferences.showHiddenRowsAndColumns
      ? rawRows.map((_, index) => index)
      : rawRows.map((_, index) => index).filter((index) => !hiddenRows.has(index));

    return visibleRows.map((index) => index + 1);
  }, [displayPreferences.showHiddenRowsAndColumns, hiddenRows, rawRows]);

  const previewCellFormats = useMemo<PreviewCellFormat[]>(() => {
    const rowPositionByOriginalIndex = new Map<number, number>();
    rowNumbers.forEach((rowNumber, displayIndex) => {
      rowPositionByOriginalIndex.set(rowNumber - 1, displayIndex);
    });

    const columnPositionByOriginalIndex = new Map<number, number>();
    visibleIndices.forEach((columnIndex, displayIndex) => {
      columnPositionByOriginalIndex.set(columnIndex, displayIndex);
    });

    return (previewQuery.data?.cellFormats ?? []).flatMap((format) => {
      const row = rowPositionByOriginalIndex.get(format.row);
      const column = columnPositionByOriginalIndex.get(format.column);
      if (row === undefined || column === undefined) {
        return [];
      }
      return [{ ...format, row, column }];
    });
  }, [previewQuery.data?.cellFormats, rowNumbers, visibleIndices]);

  const visibleColumnCount = useMemo(
    () => visibleIndices.filter((idx) => idx < rawColumnCount).length,
    [visibleIndices, rawColumnCount],
  );

  const columnLabels = useMemo(() => {
    return visibleIndices.map((index) => spreadsheetColumnLabel(index));
  }, [visibleIndices]);

  const previewMeta = useMemo(() => {
    if (!previewQuery.data) {
      return null;
    }

    const { totalRows, totalColumns, truncatedRows, truncatedColumns } = previewQuery.data;
    if (typeof totalRows !== "number" || typeof totalColumns !== "number") {
      return null;
    }

    return {
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns,
    };
  }, [previewQuery.data]);

  const previewCountSummary = useMemo(
    () =>
      buildPreviewCountSummary({
        previewMeta,
        visibleRowCount: previewRows.length,
        visibleColumnCount,
      }),
    [previewMeta, previewRows.length, visibleColumnCount],
  );

  return {
    sheets,
    selectedSheet,
    previewRows,
    rowNumbers,
    columnLabels,
    cellFormats: previewCellFormats,
    previewMeta,
    previewCountSummary,
    normalizedState,
    canLoadSelectedSource,
    isLoading: sheetsQuery.isLoading || previewQuery.isLoading,
    hasSheetError: sheetsQuery.isError,
    hasPreviewError: previewQuery.isError,
  };
}
