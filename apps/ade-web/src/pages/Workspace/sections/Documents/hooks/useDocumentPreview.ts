import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchDocumentPreview,
  fetchDocumentSheets,
  type DocumentSheet,
  type WorkbookSheetPreview,
} from "@/api/documents";

const DEFAULT_PREVIEW_ROWS = 200;
const DEFAULT_PREVIEW_COLUMNS = 50;

export function useDocumentPreview({
  workspaceId,
  documentId,
  sheetIndex,
  maxRows = DEFAULT_PREVIEW_ROWS,
  maxColumns = DEFAULT_PREVIEW_COLUMNS,
  enabled = true,
}: {
  workspaceId: string;
  documentId: string | null;
  sheetIndex: number | null;
  maxRows?: number;
  maxColumns?: number;
  enabled?: boolean;
}) {
  const sheetsQuery = useQuery<DocumentSheet[]>({
    queryKey: ["document-sheets", workspaceId, documentId],
    queryFn: ({ signal }) => {
      if (!documentId) {
        return Promise.resolve([]);
      }
      return fetchDocumentSheets(workspaceId, documentId, signal);
    },
    enabled: enabled && Boolean(workspaceId && documentId),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });

  const previewQuery = useQuery<WorkbookSheetPreview>({
    queryKey: ["document-preview", workspaceId, documentId, sheetIndex, maxRows, maxColumns],
    queryFn: ({ signal }) => {
      if (!documentId || sheetIndex === null) {
        throw new Error("Document preview requires a document and sheet.");
      }
      return fetchDocumentPreview(
        workspaceId,
        documentId,
        {
          maxRows,
          maxColumns,
          sheetIndex,
        },
        signal,
      );
    },
    enabled: enabled && Boolean(workspaceId && documentId) && sheetIndex !== null,
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
