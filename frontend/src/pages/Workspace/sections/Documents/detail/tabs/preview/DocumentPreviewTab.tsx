import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { saveRunOutputEdits } from "@/api/runs/api";
import { useNotifications } from "@/providers/notifications";
import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { DocumentPreviewGrid } from "./components/DocumentPreviewGrid";
import { DocumentPreviewHeader } from "./components/DocumentPreviewHeader";
import { DocumentPreviewSheetTabs } from "./components/DocumentPreviewSheetTabs";
import { DocumentPreviewStatsRow } from "./components/DocumentPreviewStatsRow";
import { DocumentPreviewUnavailableState } from "./components/DocumentPreviewUnavailableState";
import { useDocumentPreviewModel } from "./hooks/useDocumentPreviewModel";
import { usePreviewDisplayPreferences } from "./hooks/usePreviewDisplayPreferences";

// Feature flag to control normalized preview editing.
// Set to true to re-enable editing normalized previews and saving changes back to the database.
const ENABLE_PREVIEW_EDITING = false;

export function DocumentPreviewTab({
  workspaceId,
  document,
  source,
  sheet,
  onSourceChange,
  onSheetChange,
}: {
  workspaceId: string;
  document: DocumentRow;
  source: DocumentPreviewSource;
  sheet: string | null;
  onSourceChange: (source: DocumentPreviewSource) => void;
  onSheetChange: (sheet: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const { notifyToast } = useNotifications();

  const {
    preferences,
    showHiddenRowsAndColumns,
    setShowHiddenRowsAndColumns,
  } = usePreviewDisplayPreferences(workspaceId);

  const model = useDocumentPreviewModel({
    workspaceId,
    document,
    source,
    sheet,
    onSheetChange,
    displayPreferences: preferences,
  });

  const [editedRows, setEditedRows] = useState<string[][] | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedColumnForPopup, setSelectedColumnForPopup] = useState<{
    title: string;
    originalName: string;
  } | null>(null);

  const handleHeaderMenuClick = useCallback((gridColumnIndex: number) => {
    // Map grid visible column index to sheet physical column index
    const physicalIndex = model.visibleIndices?.[gridColumnIndex];
    if (physicalIndex === undefined) return;

    // Search in document's column mapping telemetry
    const activeSheetName = sheet || (model.selectedSheet?.name ?? null);
    const lastRunTableColumns = document.lastRunTableColumns;

    let mapping = null;
    const columnName = model.previewRows?.[0]?.[gridColumnIndex];

    if (source === "normalized") {
      // In normalized mode, the columns shown are the output schema columns.
      // Get the column name from row 0 of the visible columns.
      if (columnName) {
        const normName = columnName.toLowerCase();
        // Try matching by name and active sheet
        mapping = lastRunTableColumns?.find((col) => 
          (col.header_raw?.toLowerCase() === normName ||
           col.header_normalized?.toLowerCase() === normName ||
           col.mapped_field?.toLowerCase() === normName) && 
          col.sheet_name === activeSheetName
        );
        // Fallback to matching by name only (across any sheet)
        if (!mapping) {
          mapping = lastRunTableColumns?.find((col) => 
            col.header_raw?.toLowerCase() === normName ||
            col.header_normalized?.toLowerCase() === normName ||
            col.mapped_field?.toLowerCase() === normName
          );
        }
      }
    } else {
      // In original mode, column indexes map directly to the original sheet's columns
      mapping = lastRunTableColumns?.find((col) => 
        col.sheet_name === activeSheetName && col.column_index === physicalIndex
      );
      // Fallback: If index lookup failed but we have a columnName from row 0, match by name
      if (!mapping && columnName) {
        const normName = columnName.toLowerCase();
        mapping = lastRunTableColumns?.find((col) => 
          (col.header_raw?.toLowerCase() === normName ||
           col.header_normalized?.toLowerCase() === normName ||
           col.mapped_field?.toLowerCase() === normName) &&
          col.sheet_name === activeSheetName
        );
      }
    }

    const originalName = mapping?.header_raw ?? "no original column";
    const columnLabel = model.columnLabels[gridColumnIndex] || spreadsheetColumnLabel(physicalIndex);

    setSelectedColumnForPopup({
      title: columnLabel,
      originalName,
    });
  }, [model.visibleIndices, model.columnLabels, model.previewRows, model.selectedSheet?.name, document.lastRunTableColumns, sheet, source]);

  // Reset editedRows when switching sheet, source, or when preview rows change
  useEffect(() => {
    setEditedRows(null);
  }, [source, sheet, model.previewRows]);

  const handleRowsChange = useCallback((nextRows: string[][]) => {
    setEditedRows(nextRows);
  }, []);

  const handleSave = useCallback(async () => {
    if (!editedRows) return;

    const runId = document.lastRun?.id;
    if (!runId) {
      notifyToast({
        title: "No run output available to save edits to.",
        intent: "danger",
        duration: 5000,
      });
      return;
    }

    setIsSaving(true);
    try {
      await saveRunOutputEdits(workspaceId, runId, {
        sheetName: sheet,
        sheetIndex: model.selectedSheet?.index ?? null,
        rows: editedRows,
      });

      notifyToast({
        title: "Spreadsheet changes saved successfully.",
        intent: "success",
        duration: 3500,
      });

      // Invalidate preview queries to fetch the newly written file
      await queryClient.invalidateQueries({
        queryKey: ["document-detail-preview-grid", workspaceId, document.id],
      });
      await queryClient.invalidateQueries({
        queryKey: ["document-detail-preview-sheets", workspaceId, document.id],
      });
      // Also invalidate run and document cache so updates propagate
      await queryClient.invalidateQueries({
        queryKey: ["runs"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["documents"],
      });

      setEditedRows(null);
    } catch (error: unknown) {
      console.error("Failed to save output edits:", error);
      notifyToast({
        title: error instanceof Error ? error.message : "Failed to save changes back to the database.",
        intent: "danger",
        duration: 5000,
      });
    } finally {
      setIsSaving(false);
    }
  }, [editedRows, workspaceId, document.id, document.lastRun?.id, sheet, model.selectedSheet?.index, notifyToast, queryClient]);

  const isDirty = ENABLE_PREVIEW_EDITING && editedRows !== null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-muted/10">
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90">
        <DocumentPreviewHeader
          name={document.name}
          source={source}
          onSourceChange={onSourceChange}
          isDirty={isDirty}
          isSaving={isSaving}
          onSave={handleSave}
        />

        {model.canLoadSelectedSource ? (
          <DocumentPreviewStatsRow
            previewCountSummary={model.previewCountSummary}
            showHiddenRowsAndColumns={showHiddenRowsAndColumns}
            onShowHiddenRowsAndColumnsChange={setShowHiddenRowsAndColumns}
            metrics={document.lastRunMetrics}
          />
        ) : null}
      </div>

      {!model.canLoadSelectedSource ? (
        <DocumentPreviewUnavailableState
          reason={model.normalizedState.reason ?? "Normalized output is unavailable for this document."}
          onSwitchToOriginal={() => onSourceChange("original")}
        />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 p-4">
            <DocumentPreviewGrid
              hasSheetError={model.hasSheetError}
              hasPreviewError={model.hasPreviewError}
              isLoading={model.isLoading}
              hasSheets={model.sheets.length > 0}
              hasData={Boolean(model.selectedSheet)}
              rows={model.previewRows}
              rowNumbers={model.rowNumbers}
              columnLabels={model.columnLabels}
              cellFormats={model.cellFormats}
              isReadOnly={!ENABLE_PREVIEW_EDITING || source === "original"}
              onRowsChange={handleRowsChange}
              onHeaderMenuClick={handleHeaderMenuClick}
              className="h-full"
            />
          </div>

          <DocumentPreviewSheetTabs
            sheets={model.sheets}
            selectedSheetName={model.selectedSheet?.name ?? null}
            isLoading={model.isLoading}
            onSheetSelect={onSheetChange}
          />
        </div>
      )}

      <Dialog
        open={selectedColumnForPopup !== null}
        onOpenChange={(open) => !open && setSelectedColumnForPopup(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Column Original Header Info</DialogTitle>
            <DialogDescription>
              Introspected original column name from raw input file.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="flex flex-col gap-2 rounded-lg bg-muted/30 p-4 border border-border">
              <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                Preview Column Label
              </div>
              <div className="text-base font-bold text-foreground">
                Column {selectedColumnForPopup?.title}
              </div>
            </div>
            <div className="flex flex-col gap-2 rounded-lg bg-muted/30 p-4 border border-border">
              <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                Original Column Name
              </div>
              <div className="text-base font-bold text-foreground">
                {selectedColumnForPopup?.originalName === "no original column" ? (
                  <span className="text-muted-foreground italic font-medium">no original column</span>
                ) : (
                  <span className="text-primary">{selectedColumnForPopup?.originalName}</span>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="secondary">
                Dismiss
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
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
