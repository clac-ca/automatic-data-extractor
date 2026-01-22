import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchRunOutputPreview,
  fetchRunOutputSheets,
  type RunOutputSheet,
  type WorkbookSheetPreview,
} from "@/api/runs/api";

export function useRunOutputPreview({
  runId,
  sheetIndex,
  maxRows,
  maxColumns,
  trimEmptyRows = false,
  trimEmptyColumns = false,
  enabled = true,
}: {
  runId: string | null;
  sheetIndex: number | null;
  maxRows?: number;
  maxColumns?: number;
  trimEmptyRows?: boolean;
  trimEmptyColumns?: boolean;
  enabled?: boolean;
}) {
  const sheetsQuery = useQuery<RunOutputSheet[]>({
    queryKey: ["run-output-sheets", runId],
    queryFn: ({ signal }) => {
      if (!runId) {
        return Promise.resolve([]);
      }
      return fetchRunOutputSheets(runId, signal);
    },
    enabled: enabled && Boolean(runId),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });

  const previewQuery = useQuery<WorkbookSheetPreview>({
    queryKey: [
      "run-output-preview",
      runId,
      sheetIndex,
      maxRows,
      maxColumns,
      trimEmptyRows,
      trimEmptyColumns,
    ],
    queryFn: ({ signal }) => {
      if (!runId || sheetIndex === null) {
        throw new Error("Run output preview requires a run and sheet.");
      }
      return fetchRunOutputPreview(
        runId,
        {
          maxRows,
          maxColumns,
          trimEmptyRows,
          trimEmptyColumns,
          sheetIndex,
        },
        signal,
      );
    },
    enabled: enabled && Boolean(runId) && sheetIndex !== null,
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });

  const sheets = sheetsQuery.data ?? [];
  const activeSheet = useMemo(
    () => sheets.find((sheet) => sheet.is_active) ?? sheets[0] ?? null,
    [sheets],
  );

  return {
    sheets,
    activeSheet,
    preview: previewQuery.data ?? null,
    isSheetsLoading: sheetsQuery.isLoading,
    isSheetsFetching: sheetsQuery.isFetching,
    sheetsError: sheetsQuery.error instanceof Error ? sheetsQuery.error.message : null,
    isPreviewLoading: previewQuery.isLoading,
    isPreviewFetching: previewQuery.isFetching,
    previewError: previewQuery.error instanceof Error ? previewQuery.error.message : null,
  };
}
