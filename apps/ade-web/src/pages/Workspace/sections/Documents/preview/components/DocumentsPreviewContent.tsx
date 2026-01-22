import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { DocumentsPreviewSkeleton } from "./DocumentsPreviewSkeleton";
import { DocumentsPreviewGrid } from "./DocumentsPreviewGrid";
import { buildPreviewGridModel } from "../lib/previewGridModel";
import { useDocumentPreview } from "../../hooks/useDocumentPreview";
import { useRunOutputPreview } from "../../hooks/useRunOutputPreview";
import type { DocumentRow } from "../../types";

type PreviewVariant = "normalized" | "original";

export function DocumentsPreviewContent({
  workspaceId,
  document,
  onDownloadOriginal,
  onDownloadOutput,
}: {
  workspaceId: string;
  document: DocumentRow;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onDownloadOutput?: (document: DocumentRow) => void;
}) {
  const normalizedRunId = document.lastRun?.status === "succeeded" ? document.lastRun.id : null;
  const hasNormalizedOutput = Boolean(normalizedRunId);
  const [previewVariant, setPreviewVariant] = useState<PreviewVariant>(
    hasNormalizedOutput ? "normalized" : "original",
  );
  const [sheetIndex, setSheetIndex] = useState<number | null>(null);

  useEffect(() => {
    setSheetIndex(null);
    setPreviewVariant(hasNormalizedOutput ? "normalized" : "original");
  }, [document.id, hasNormalizedOutput]);

  const originalPreview = useDocumentPreview({
    workspaceId,
    documentId: document.id,
    sheetIndex,
    trimEmptyRows: true,
    trimEmptyColumns: true,
    enabled: previewVariant === "original",
  });

  const normalizedPreview = useRunOutputPreview({
    runId: normalizedRunId,
    sheetIndex,
    trimEmptyRows: true,
    trimEmptyColumns: true,
    enabled: previewVariant === "normalized",
  });

  const previewState = previewVariant === "normalized" ? normalizedPreview : originalPreview;
  const {
    sheets,
    activeSheet,
    preview,
    isSheetsLoading,
    sheetsError,
    isPreviewLoading,
    isPreviewFetching,
    previewError,
  } = previewState;

  useEffect(() => {
    if (sheetIndex !== null) return;
    if (!activeSheet) return;
    setSheetIndex(activeSheet.index);
  }, [activeSheet, sheetIndex]);

  const handlePreviewVariantChange = (nextVariant: PreviewVariant) => {
    if (nextVariant === previewVariant) return;
    setSheetIndex(null);
    setPreviewVariant(nextVariant);
  };

  const previewRows = preview?.rows ?? [];
  const previewModel = useMemo(
    () => buildPreviewGridModel(previewRows),
    [previewRows],
  );
  const resetKey = `${document.id}:${previewVariant}:${sheetIndex ?? "none"}`;

  const visibleRows = previewModel.bodyRows.length;
  const totalRows = preview?.totalRows ?? 0;
  const totalColumns = preview?.totalColumns ?? 0;
  const visibleColumns = previewModel.columnCount;
  const truncatedRows = preview?.truncatedRows ?? false;
  const truncatedColumns = preview?.truncatedColumns ?? false;

  const summaryLabel = preview
    ? `Showing ${visibleRows} of ${totalRows} rows · ${visibleColumns} of ${totalColumns} columns`
    : "Preparing preview";

  const truncationLabel =
    preview && (truncatedRows || truncatedColumns)
      ? "Preview is truncated"
      : null;

  const showSkeleton = (isSheetsLoading || isPreviewLoading) && !preview;
  const showRefreshing = Boolean(preview) && isPreviewFetching;

  const showError = Boolean(previewError || sheetsError);

  const hasSheets = sheets.length > 0;
  const selectedSheetValue = sheetIndex !== null ? String(sheetIndex) : "";
  const showNormalizedNotice = !hasNormalizedOutput;

  const canDownloadOriginal = Boolean(onDownloadOriginal);
  const canDownloadNormalized = Boolean(onDownloadOutput && normalizedRunId);
  const canDownloadAny = canDownloadOriginal || canDownloadNormalized;
  const isNormalizedView = previewVariant === "normalized";
  const downloadLabel = isNormalizedView ? "Download normalized" : "Download original";
  const downloadDisabled = isNormalizedView ? !canDownloadNormalized : !canDownloadOriginal;
  const downloadTitle = isNormalizedView
    ? canDownloadNormalized
      ? "Download normalized output"
      : hasNormalizedOutput
        ? "Download unavailable"
        : "No normalized output available yet"
    : canDownloadOriginal
      ? "Download original document"
      : "Download unavailable";

  const handleDownload = () => {
    if (isNormalizedView) {
      onDownloadOutput?.(document);
      return;
    }
    onDownloadOriginal?.(document);
  };

  const runInsights = useMemo(() => {
    const insights: Array<{ label: string; value: string }> = [];
    const metrics = document.lastRunMetrics ?? null;
    const columns = document.lastRunTableColumns ?? null;
    const fields = document.lastRunFields ?? null;

    if (metrics?.evaluation_outcome) {
      insights.push({
        label: "Eval",
        value: metrics.evaluation_outcome.replace(/_/g, " "),
      });
    }

    if (Array.isArray(columns) && columns.length > 0) {
      const mapped = columns.filter((column) => column.mapping_status === "mapped").length;
      insights.push({
        label: "Mapped columns",
        value: `${mapped}/${columns.length}`,
      });
    }

    if (Array.isArray(fields) && fields.length > 0) {
      const detected = fields.filter((field) => field.detected).length;
      insights.push({
        label: "Detected fields",
        value: `${detected}/${fields.length}`,
      });
    }

    return insights;
  }, [document.lastRunFields, document.lastRunMetrics, document.lastRunTableColumns]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-3 bg-background px-6 py-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-3">
          <PreviewVariantToggle
            value={previewVariant}
            onChange={handlePreviewVariantChange}
            hasNormalizedOutput={hasNormalizedOutput}
          />
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-muted-foreground">Sheet</span>
            <Select
              value={selectedSheetValue}
              onValueChange={(value) => setSheetIndex(Number(value))}
              disabled={!hasSheets}
            >
              <SelectTrigger className="h-7 w-[180px] bg-background text-xs">
                <SelectValue placeholder={hasSheets ? "Select sheet" : "No sheets"} />
              </SelectTrigger>
              <SelectContent>
                {sheets.map((sheet) => (
                  <SelectItem key={sheet.index} value={String(sheet.index)}>
                    {sheet.name || `Sheet ${sheet.index + 1}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span>{summaryLabel}</span>
          {truncationLabel ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              {truncationLabel}
            </span>
          ) : null}
          {runInsights.map((insight) => (
            <span
              key={insight.label}
              className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
            >
              <span className="font-medium text-foreground">{insight.label}</span>
              <span className="ml-1 tabular-nums">{insight.value}</span>
            </span>
          ))}
          {showNormalizedNotice ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              No normalized output yet
            </span>
          ) : null}
          {showRefreshing ? (
            <span className="text-[10px] text-muted-foreground">Refreshing…</span>
          ) : null}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {canDownloadAny ? (
            <Button
              size="sm"
              variant="default"
              onClick={handleDownload}
              disabled={downloadDisabled}
              title={downloadTitle}
            >
              {downloadLabel}
            </Button>
          ) : null}
        </div>
      </div>
      <Separator />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {showSkeleton ? (
          <div className="px-6">
            <DocumentsPreviewSkeleton columnCount={Math.max(4, visibleColumns || 6)} />
          </div>
        ) : showError ? (
          <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
            Unable to load the document preview. Try again later.
          </div>
        ) : preview ? (
          <div className="flex min-h-0 min-w-0 flex-1 flex-col px-6 py-4">
            <DocumentsPreviewGrid
              key={resetKey}
              headerRow={previewModel.headerRow}
              rows={previewModel.bodyRows}
              columnCount={previewModel.columnCount}
              resetKey={resetKey}
            />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
            Preview not available for this document.
          </div>
        )}
      </div>
    </div>
  );
}

function PreviewVariantToggle({
  value,
  onChange,
  hasNormalizedOutput,
}: {
  value: PreviewVariant;
  onChange: (value: PreviewVariant) => void;
  hasNormalizedOutput: boolean;
}) {
  return (
    <div
      className="flex items-center gap-1 rounded-full border border-border bg-muted/40 p-0.5"
      role="group"
      aria-label="Preview source"
    >
      <Button
        size="sm"
        variant={value === "normalized" ? "secondary" : "ghost"}
        className="h-6 rounded-full px-2 text-[11px]"
        onClick={() => onChange("normalized")}
        disabled={!hasNormalizedOutput}
        aria-pressed={value === "normalized"}
        title={
          hasNormalizedOutput ? "Preview normalized output" : "No normalized output available yet"
        }
      >
        Normalized
      </Button>
      <Button
        size="sm"
        variant={value === "original" ? "secondary" : "ghost"}
        className="h-6 rounded-full px-2 text-[11px]"
        onClick={() => onChange("original")}
        aria-pressed={value === "original"}
        title="Preview original document"
      >
        Original
      </Button>
    </div>
  );
}
