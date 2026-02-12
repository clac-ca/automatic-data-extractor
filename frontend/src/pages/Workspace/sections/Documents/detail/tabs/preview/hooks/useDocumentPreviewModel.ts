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

const DEFAULT_MAX_ROWS = 200;
const DEFAULT_MAX_COLUMNS = 50;

export function resolveVisibleColumnCount(
  rows: string[][],
  totalColumns: number | undefined,
  maxColumns = DEFAULT_MAX_COLUMNS,
) {
  const returnedWidth = rows.reduce((max, row) => Math.max(max, row.length), 0);
  if (returnedWidth > 0) {
    return returnedWidth;
  }

  if (typeof totalColumns === "number") {
    return Math.max(0, Math.min(totalColumns, maxColumns));
  }

  return 0;
}

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
}: {
  workspaceId: string;
  document: DocumentRow;
  source: DocumentPreviewSource;
  sheet: string | null;
  onSheetChange: (sheet: string | null) => void;
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
    ],
    queryFn: ({ signal }) => {
      const options = {
        maxRows: DEFAULT_MAX_ROWS,
        maxColumns: DEFAULT_MAX_COLUMNS,
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

  const previewRows = useMemo(() => previewQuery.data?.rows ?? [], [previewQuery.data]);

  const columnLabels = useMemo(() => {
    const fallbackColumnCount = resolveVisibleColumnCount(
      previewRows,
      previewQuery.data?.totalColumns,
    );

    return Array.from({ length: fallbackColumnCount }, (_, index) => spreadsheetColumnLabel(index));
  }, [previewQuery.data?.totalColumns, previewRows]);

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
      visibleColumns: resolveVisibleColumnCount(previewRows, totalColumns),
      truncatedRows,
      truncatedColumns,
    };
  }, [previewQuery.data, previewRows]);

  return {
    sheets,
    selectedSheet,
    previewRows,
    columnLabels,
    previewMeta,
    normalizedState,
    canLoadSelectedSource,
    isLoading: sheetsQuery.isLoading || previewQuery.isLoading,
    hasSheetError: sheetsQuery.isError,
    hasPreviewError: previewQuery.isError,
  };
}
