import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentPreviewGrid } from "./components/DocumentPreviewGrid";
import { DocumentPreviewHeader } from "./components/DocumentPreviewHeader";
import { DocumentPreviewSheetTabs } from "./components/DocumentPreviewSheetTabs";
import { DocumentPreviewStatsRow } from "./components/DocumentPreviewStatsRow";
import { DocumentPreviewUnavailableState } from "./components/DocumentPreviewUnavailableState";
import { useDocumentPreviewModel } from "./hooks/useDocumentPreviewModel";
import { usePreviewDisplayPreferences } from "./hooks/usePreviewDisplayPreferences";

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
  const {
    preferences,
    isCompactMode,
    setCompactMode,
  } = usePreviewDisplayPreferences(workspaceId);

  const model = useDocumentPreviewModel({
    workspaceId,
    document,
    source,
    sheet,
    onSheetChange,
    displayPreferences: preferences,
  });

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-muted/10">
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90">
        <DocumentPreviewHeader
          name={document.name}
          source={source}
          onSourceChange={onSourceChange}
        />

        {model.canLoadSelectedSource ? (
          <DocumentPreviewStatsRow
            previewCountSummary={model.previewCountSummary}
            isCompactMode={isCompactMode}
            onCompactModeChange={setCompactMode}
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
              columnLabels={model.columnLabels}
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
    </div>
  );
}
