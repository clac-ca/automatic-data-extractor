import { useEffect, useMemo, useState } from "react";

import { fetchDocumentSheets } from "@/api/documents";
import type { RunStreamOptions } from "@/api/runs/api";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RefreshIcon } from "@/components/icons";
import { cn } from "@/lib/utils";

import type { FileType } from "../../shared/types";
import { fileTypeLabel } from "../../shared/utils";
import {
  buildUploadRunOptions,
  normalizeSheetNames,
  supportsWorkbookSheetSelection,
  type UploadSheetScope,
} from "./sheetSelection";

export type ReprocessTargetDocument = {
  readonly id: string;
  readonly name: string;
  readonly fileType: FileType;
};

type ReprocessPreflightDialogProps = {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly documents: ReprocessTargetDocument[];
  readonly onConfirm: (runOptions: Pick<RunStreamOptions, "active_sheet_only" | "input_sheet_names">) => void;
  readonly onCancel: () => void;
  readonly processingPaused: boolean;
  readonly configMissing: boolean;
  readonly isSubmitting?: boolean;
};

export function ReprocessPreflightDialog({
  open,
  workspaceId,
  documents,
  onConfirm,
  onCancel,
  processingPaused,
  configMissing,
  isSubmitting = false,
}: ReprocessPreflightDialogProps) {
  const [sheetScope, setSheetScope] = useState<UploadSheetScope>("active");
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [workbookSheets, setWorkbookSheets] = useState<string[]>([]);
  const [isLoadingWorkbookSheets, setIsLoadingWorkbookSheets] = useState(false);
  const [workbookSheetError, setWorkbookSheetError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setSheetScope("active");
      setSelectedSheets([]);
      setWorkbookSheets([]);
      setIsLoadingWorkbookSheets(false);
      setWorkbookSheetError(null);
      return;
    }
    setSheetScope("active");
    setSelectedSheets([]);
    setWorkbookSheets([]);
    setIsLoadingWorkbookSheets(false);
    setWorkbookSheetError(null);
  }, [open]);

  const singleWorkbookDocument = useMemo(() => {
    if (documents.length !== 1) {
      return null;
    }
    const [entry] = documents;
    if (!entry || !supportsWorkbookSheetSelection(entry.fileType)) {
      return null;
    }
    return entry;
  }, [documents]);

  useEffect(() => {
    let cancelled = false;
    if (!open || !singleWorkbookDocument) {
      setWorkbookSheets([]);
      setIsLoadingWorkbookSheets(false);
      setWorkbookSheetError(null);
      setSelectedSheets([]);
      setSheetScope((current) => (current === "selected" ? "active" : current));
      return () => {
        cancelled = true;
      };
    }

    setIsLoadingWorkbookSheets(true);
    setWorkbookSheetError(null);
    setWorkbookSheets([]);
    fetchDocumentSheets(workspaceId, singleWorkbookDocument.id)
      .then((sheets) => {
        if (cancelled) return;
        const sheetNames = normalizeSheetNames(sheets.map((sheet) => sheet.name));
        setWorkbookSheets(sheetNames);
        if (sheetNames.length === 0) {
          setSheetScope((current) => (current === "selected" ? "active" : current));
          setSelectedSheets([]);
          setWorkbookSheetError("No worksheets were found in this workbook.");
          return;
        }
        setSelectedSheets((current) =>
          current.filter((sheetName) => sheetNames.includes(sheetName)),
        );
      })
      .catch(() => {
        if (cancelled) return;
        setSheetScope((current) => (current === "selected" ? "active" : current));
        setSelectedSheets([]);
        setWorkbookSheetError("Unable to load worksheet names for this workbook.");
      })
      .finally(() => {
        if (cancelled) return;
        setIsLoadingWorkbookSheets(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, singleWorkbookDocument, workspaceId]);

  const normalizedSelectedSheets = useMemo(() => {
    const available = new Set(workbookSheets);
    const unique = new Set<string>();
    for (const sheetName of selectedSheets) {
      if (!available.has(sheetName)) {
        continue;
      }
      unique.add(sheetName);
    }
    return Array.from(unique);
  }, [selectedSheets, workbookSheets]);

  const specificScopeEnabled =
    Boolean(singleWorkbookDocument) && workbookSheets.length > 0 && !isLoadingWorkbookSheets;
  const allSheetsSelected =
    workbookSheets.length > 0 && normalizedSelectedSheets.length === workbookSheets.length;
  const confirmationDisabled =
    documents.length === 0
    || isSubmitting
    || (
      sheetScope === "selected"
      && (!specificScopeEnabled || normalizedSelectedSheets.length === 0)
    );
  const scopeAppliesLabel =
    documents.length <= 1
      ? "Applies to this document."
      : `Applies to all ${documents.length} selected documents.`;

  const summaryLabel = useMemo(() => {
    if (documents.length === 0) return "No documents selected";
    if (documents.length === 1) return documents[0]?.name ?? "Document";
    return `${documents.length} documents selected`;
  }, [documents]);

  const toggleSheetSelection = (sheetName: string) => {
    setSelectedSheets((current) =>
      current.includes(sheetName)
        ? current.filter((value) => value !== sheetName)
        : [...current, sheetName],
    );
  };

  const selectAllSheets = () => {
    setSelectedSheets(workbookSheets);
  };

  const handleConfirm = () => {
    if (!documents.length || isSubmitting) return;
    const runOptions = buildUploadRunOptions(sheetScope, normalizedSelectedSheets);
    onConfirm(runOptions);
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onCancel() : undefined)}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Reprocess documents</DialogTitle>
          <DialogDescription>{summaryLabel}</DialogDescription>
        </DialogHeader>

        {(processingPaused || configMissing) && (
          <Alert tone="warning" className="text-sm">
            {processingPaused
              ? "Processing is paused. Runs will queue until processing resumes."
              : "No active configuration. Runs will queue until a configuration is active."}
          </Alert>
        )}

        <div className="space-y-3 rounded-xl border border-border/80 bg-muted/20 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">Worksheet processing</p>
              <p className="text-xs text-muted-foreground">
                Choose how worksheets should be processed for this re-run.
              </p>
            </div>
            <p className="rounded-full bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground">
              {scopeAppliesLabel}
            </p>
          </div>

          <div className="space-y-2">
            <div
              className={cn(
                "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                sheetScope === "active"
                  ? "border-primary/70 bg-primary/5"
                  : "border-border bg-background hover:border-primary/40",
              )}
            >
              <input
                id="reprocess-sheet-scope-active"
                type="radio"
                name="reprocess-sheet-scope"
                className="mt-0.5 h-4 w-4"
                checked={sheetScope === "active"}
                onChange={() => setSheetScope("active")}
              />
              <span className="space-y-0.5">
                <label htmlFor="reprocess-sheet-scope-active" className="block font-medium text-foreground">
                  Active sheet only
                </label>
                <span className="block text-xs text-muted-foreground">
                  Default. Processes the workbook active sheet when applicable.
                </span>
              </span>
            </div>

            <div
              className={cn(
                "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                sheetScope === "all"
                  ? "border-primary/70 bg-primary/5"
                  : "border-border bg-background hover:border-primary/40",
              )}
            >
              <input
                id="reprocess-sheet-scope-all"
                type="radio"
                name="reprocess-sheet-scope"
                className="mt-0.5 h-4 w-4"
                checked={sheetScope === "all"}
                onChange={() => setSheetScope("all")}
              />
              <span className="space-y-0.5">
                <label htmlFor="reprocess-sheet-scope-all" className="block font-medium text-foreground">
                  All sheets
                </label>
                <span className="block text-xs text-muted-foreground">
                  Processes every worksheet in each workbook.
                </span>
              </span>
            </div>

            {singleWorkbookDocument ? (
              <div
                className={cn(
                  "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                  sheetScope === "selected"
                    ? "border-primary/70 bg-primary/5"
                    : "border-border bg-background hover:border-primary/40",
                  !specificScopeEnabled && "opacity-60",
                )}
              >
                <input
                  id="reprocess-sheet-scope-selected"
                  type="radio"
                  name="reprocess-sheet-scope"
                  className="mt-0.5 h-4 w-4"
                  checked={sheetScope === "selected"}
                  onChange={() => setSheetScope("selected")}
                  disabled={!specificScopeEnabled}
                />
                <span className="space-y-0.5">
                  <label htmlFor="reprocess-sheet-scope-selected" className="block font-medium text-foreground">
                    Specific sheets
                  </label>
                  <span className="block text-xs text-muted-foreground">
                    Choose one or more worksheets from this document.
                  </span>
                </span>
              </div>
            ) : null}
          </div>

          {singleWorkbookDocument ? (
            <div
              className={cn(
                "rounded-lg border border-border bg-background p-2 transition-opacity",
                sheetScope !== "selected" && "opacity-80",
              )}
            >
              {isLoadingWorkbookSheets ? (
                <p className="text-xs text-muted-foreground">Loading worksheets…</p>
              ) : workbookSheetError ? (
                <Alert tone="warning" className="text-xs">
                  {workbookSheetError}
                </Alert>
              ) : workbookSheets.length > 0 ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-foreground">
                      Worksheets ({workbookSheets.length.toLocaleString()})
                    </p>
                    <div className="flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={selectAllSheets}
                        disabled={sheetScope !== "selected" || allSheetsSelected}
                      >
                        Select all
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => setSelectedSheets([])}
                        disabled={sheetScope !== "selected" || normalizedSelectedSheets.length === 0}
                      >
                        Clear
                      </Button>
                    </div>
                  </div>
                  <div className="max-h-36 space-y-1 overflow-y-auto rounded-md border border-border p-1">
                    {workbookSheets.map((sheetName) => {
                      const checked = normalizedSelectedSheets.includes(sheetName);
                      return (
                        <label
                          key={sheetName}
                          className={cn(
                            "flex items-center gap-2 rounded px-2 py-1 text-xs text-foreground",
                            sheetScope === "selected" ? "hover:bg-muted" : "opacity-80",
                          )}
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4"
                            checked={checked}
                            onChange={() => toggleSheetSelection(sheetName)}
                            disabled={sheetScope !== "selected"}
                          />
                          <span className="truncate">{sheetName}</span>
                        </label>
                      );
                    })}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {sheetScope === "selected"
                      ? normalizedSelectedSheets.length === 0
                        ? "Select at least one worksheet to continue."
                        : `${normalizedSelectedSheets.length.toLocaleString()} worksheet${
                            normalizedSelectedSheets.length === 1 ? "" : "s"
                          } selected.`
                      : "Switch to Specific sheets to choose worksheets manually."}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No worksheets available for selection.</p>
              )}
            </div>
          ) : null}
        </div>

        <div className="mt-2 max-h-64 space-y-2 overflow-y-auto pr-1">
          {documents.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-foreground">{entry.name}</p>
                <p className="text-[10px] text-muted-foreground">{fileTypeLabel(entry.fileType)}</p>
              </div>
            </div>
          ))}
          {documents.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
              No documents selected.
            </div>
          ) : null}
        </div>

        <DialogFooter className="mt-4 flex items-center justify-between sm:justify-between">
          <Button variant="ghost" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={confirmationDisabled} className="gap-2">
            <RefreshIcon className="h-4 w-4" />
            {isSubmitting ? "Reprocessing..." : "Reprocess"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
