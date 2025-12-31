import clsx from "clsx";
import { createPortal } from "react-dom";
import { useEffect, useMemo, useRef, useState } from "react";

import type { UploadManagerQueueItem } from "@hooks/documents/uploadManager";
import { Alert } from "@components/ui/alert";
import { Button } from "@components/ui/button";
import { CloseIcon, TrashIcon, UploadIcon } from "@components/icons";

import type { FileType } from "../types";
import { fileTypeLabel, formatBytes, inferFileType, stableId } from "../utils";

type UploadPreflightDialogProps = {
  readonly open: boolean;
  readonly files: File[];
  readonly onConfirm: (items: UploadManagerQueueItem[]) => void;
  readonly onCancel: () => void;
  readonly processingPaused: boolean;
  readonly configMissing: boolean;
};

type SheetInfo = {
  status: "idle" | "loading" | "ready" | "error";
  names: string[];
  activeName: string | null;
  error?: string;
};

type PreflightFile = {
  id: string;
  file: File;
  type: FileType;
};

type SheetMode = "active" | "all" | "custom";

export function UploadPreflightDialog({
  open,
  files,
  onConfirm,
  onCancel,
  processingPaused,
  configMissing,
}: UploadPreflightDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const [localFiles, setLocalFiles] = useState<PreflightFile[]>([]);
  const [sheetInfoById, setSheetInfoById] = useState<Record<string, SheetInfo>>({});
  const [sheetMode, setSheetMode] = useState<SheetMode>("active");
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [activeOnly, setActiveOnly] = useState(false);

  useEffect(() => {
    if (!open) {
      setLocalFiles([]);
      return;
    }
    setLocalFiles(
      files.map((file) => ({
        id: stableId(),
        file,
        type: inferFileType(file.name, file.type),
      })),
    );
  }, [files, open]);


  useEffect(() => {
    if (!open) return;
    setSheetMode("active");
    setSelectedSheets([]);
    setActiveOnly(false);
    setSheetInfoById({});
  }, [open, localFiles.length]);

  useEffect(() => {
    if (!open || localFiles.length === 0) return;
    if (localFiles.length !== 1) {
      setSheetInfoById({});
      return;
    }
    const entry = localFiles[0];
    if (!isSpreadsheet(entry.type)) {
      setSheetInfoById({
        [entry.id]: { status: "ready", names: [], activeName: null },
      });
      return;
    }
    let canceled = false;
    setSheetInfoById({
      [entry.id]: { status: "loading", names: [], activeName: null },
    });

    const parseSheets = async () => {
      try {
        const info = await inspectWorkbookFile(entry.file);
        if (canceled) return;
        setSheetInfoById({
          [entry.id]: {
            status: "ready",
            names: info.names,
            activeName: info.activeName,
          },
        });
      } catch (error) {
        if (canceled) return;
        setSheetInfoById({
          [entry.id]: {
            status: "error",
            names: [],
            activeName: null,
            error: error instanceof Error ? error.message : "Unable to read worksheets.",
          },
        });
      }
    };

    void parseSheets();
    return () => {
      canceled = true;
    };
  }, [localFiles, open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
      if (event.key === "Tab") {
        const root = dialogRef.current;
        if (!root) return;
        const focusable = Array.from(
          root.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
          ),
        ).filter((el) => !el.hasAttribute("disabled"));
        if (focusable.length === 0) return;
        const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
        const nextIndex = event.shiftKey
          ? currentIndex <= 0
            ? focusable.length - 1
            : currentIndex - 1
          : currentIndex === focusable.length - 1
            ? 0
            : currentIndex + 1;
        focusable[nextIndex]?.focus();
        event.preventDefault();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel, open]);

  useEffect(() => {
    if (!open) return;
    const { body } = document;
    const previousOverflow = body.style.overflow;
    body.style.overflow = "hidden";
    return () => {
      body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus({ preventScroll: true });
  }, [open]);

  const isSingle = localFiles.length === 1;
  const spreadsheetCount = localFiles.filter((entry) => isSpreadsheet(entry.type)).length;
  const activeFile = isSingle ? localFiles[0] : null;
  const activeFileSheetInfo = activeFile ? sheetInfoById[activeFile.id] : null;
  const activeSheetName = activeFileSheetInfo?.activeName ?? null;
  const sheetNames = activeFileSheetInfo?.names ?? [];
  const sheetStatus = activeFileSheetInfo?.status ?? "idle";
  const isActiveFileSpreadsheet = Boolean(activeFile && isSpreadsheet(activeFile.type));

  useEffect(() => {
    if (!open) return;
    if (sheetMode !== "custom") return;
    if (selectedSheets.length > 0) return;
    if (activeSheetName) {
      setSelectedSheets([activeSheetName]);
    }
  }, [activeSheetName, open, selectedSheets.length, sheetMode]);

  const confirmDisabled = useMemo(() => {
    if (localFiles.length === 0) return true;
    if (isSingle) {
      if (!isActiveFileSpreadsheet) return false;
      if (sheetMode === "all") return false;
      if (sheetMode === "custom") return selectedSheets.length === 0;
      return !activeSheetName || sheetStatus !== "ready";
    }
    return false;
  }, [
    activeSheetName,
    isActiveFileSpreadsheet,
    isSingle,
    localFiles.length,
    selectedSheets.length,
    sheetMode,
    sheetStatus,
  ]);

  const processingNote = useMemo(() => {
    if (processingPaused) {
      return "Processing is paused. Uploads will be stored until processing resumes.";
    }
    if (configMissing) {
      return "No active configuration yet. Uploads will process once one is enabled.";
    }
    return "Uploads will process automatically after they finish.";
  }, [configMissing, processingPaused]);

  if (!open || typeof document === "undefined") {
    return null;
  }

  const handleConfirm = () => {
    if (confirmDisabled) return;
    if (localFiles.length === 0) return;
    const items: UploadManagerQueueItem[] = localFiles.map((entry) => {
      if (!isSpreadsheet(entry.type)) {
        return { file: entry.file };
      }
      if (isSingle) {
        if (sheetMode === "custom" && selectedSheets.length > 0) {
          return {
            file: entry.file,
            runOptions: { input_sheet_names: selectedSheets, active_sheet_only: false },
          };
        }
        if (sheetMode === "active" && activeSheetName) {
          return { file: entry.file, runOptions: { active_sheet_only: true } };
        }
        return { file: entry.file };
      }
      if (activeOnly) {
        return { file: entry.file, runOptions: { active_sheet_only: true } };
      }
      return { file: entry.file };
    });
    onConfirm(items);
  };

  const content = (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-overlay/60 px-4 py-6"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onCancel();
        }
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-preflight-title"
        className="flex w-full max-w-2xl max-h-[90vh] flex-col overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">Upload</p>
            <h2 id="upload-preflight-title" className="text-xl font-semibold text-foreground">
              Choose sheets before upload
            </h2>
            <p className="text-sm text-muted-foreground">
              {isSingle ? "Pick the sheets to process for this file." : "Batch uploads use a shared sheet rule."}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onCancel} aria-label="Close dialog">
            <CloseIcon className="h-4 w-4" />
          </Button>
        </header>

        <div className="mt-6 flex min-h-0 flex-1 flex-col gap-6">
          <section className="flex min-h-0 flex-1 flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">
                {localFiles.length} file{localFiles.length === 1 ? "" : "s"} ready
              </h3>
              <span className="text-xs text-muted-foreground">
                Total size {formatBytes(localFiles.reduce((sum, entry) => sum + entry.file.size, 0))}
              </span>
            </div>
            <div className="flex-1 min-h-0 space-y-2 overflow-auto pr-1">
              {localFiles.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center gap-3 rounded-xl border border-border/80 bg-muted/30 px-3 py-2"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-[10px] font-semibold text-muted-foreground">
                    {fileTypeLabel(entry.type)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{entry.file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatBytes(entry.file.size)}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setLocalFiles((current) => current.filter((file) => file.id !== entry.id))
                    }
                    aria-label={`Remove ${entry.file.name}`}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-4">
            {isSingle ? (
              <div className="space-y-3">
                <div className="space-y-1">
                  <h3 className="text-sm font-semibold text-foreground">Sheet selection</h3>
                  <p className="text-xs text-muted-foreground">
                    {isActiveFileSpreadsheet
                      ? "Active sheet is recommended for most uploads."
                      : "Sheet selection is not available for this file type."}
                  </p>
                </div>

                {isActiveFileSpreadsheet && sheetStatus === "loading" ? (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
                    Reading worksheet names...
                  </div>
                ) : null}

                {isActiveFileSpreadsheet && sheetStatus === "error" ? (
                  <Alert tone="warning" heading="Worksheet metadata unavailable">
                    {activeFileSheetInfo?.error ?? "We could not read worksheets from this file."}
                  </Alert>
                ) : null}

                {!isActiveFileSpreadsheet ? (
                  <div className="rounded-lg border border-border/70 bg-muted/40 p-3 text-xs text-muted-foreground">
                    This file will be processed as a single sheet.
                  </div>
                ) : (
                  <>
                    <fieldset className="space-y-2" aria-label="Sheet selection mode">
                      <legend className="sr-only">Sheet selection mode</legend>
                      {[
                        {
                          value: "active" as const,
                          title: "Active sheet",
                          description: activeSheetName
                            ? `Active sheet: ${activeSheetName}`
                            : "Active sheet not detected",
                          disabled: sheetStatus !== "ready" || !activeSheetName,
                        },
                        {
                          value: "all" as const,
                          title: "All sheets",
                          description: "Process every sheet in the workbook.",
                          disabled: false,
                        },
                        {
                          value: "custom" as const,
                          title: "Choose sheets",
                          description: "Select specific sheets from the list.",
                          disabled: sheetStatus === "error" || sheetNames.length === 0,
                        },
                      ].map((option) => (
                        <label
                          key={option.value}
                          className={clsx(
                            "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition",
                            sheetMode === option.value
                              ? "border-brand-500 bg-brand-500/10"
                              : "border-border bg-card hover:border-muted-foreground/40",
                            option.disabled && "cursor-not-allowed opacity-60",
                          )}
                        >
                          <input
                            type="radio"
                            name="sheet-mode"
                            className="mt-1 h-4 w-4 border-border text-brand-600 focus:ring-brand-500"
                            checked={sheetMode === option.value}
                            onChange={() => setSheetMode(option.value)}
                            disabled={option.disabled}
                          />
                          <div className="space-y-1">
                            <p className="text-sm font-semibold text-foreground">{option.title}</p>
                            <p className="text-xs text-muted-foreground">{option.description}</p>
                          </div>
                        </label>
                      ))}
                    </fieldset>

                    {sheetMode === "custom" ? (
                      <div className="rounded-xl border border-border bg-muted/30 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs text-muted-foreground">
                            {selectedSheets.length === 0
                              ? "Select at least one sheet."
                              : `${selectedSheets.length} sheet${selectedSheets.length === 1 ? "" : "s"} selected`}
                          </p>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedSheets(sheetNames)}
                              disabled={sheetNames.length === 0}
                            >
                              Select all
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                              Clear
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3 max-h-48 space-y-1 overflow-auto rounded-lg border border-border bg-card/60 p-2">
                          {sheetNames.map((name) => {
                            const checked = selectedSheets.includes(name);
                            const isActive = activeSheetName === name;
                            return (
                              <label
                                key={name}
                                className="flex items-center gap-2 rounded px-2 py-1 text-sm text-foreground hover:bg-muted"
                              >
                                <input
                                  type="checkbox"
                                  className="h-4 w-4 rounded border-border text-brand-600 focus:ring-brand-500"
                                  checked={checked}
                                  onChange={() =>
                                    setSelectedSheets((current) =>
                                      current.includes(name)
                                        ? current.filter((sheet) => sheet !== name)
                                        : [...current, name],
                                    )
                                  }
                                />
                                <span className="flex-1 truncate">
                                  {name}
                                  {isActive ? " (active)" : ""}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-1">
                  <h3 className="text-sm font-semibold text-foreground">Batch rules</h3>
                  <p className="text-xs text-muted-foreground">
                    Sheet-by-sheet selection is only available for single uploads.
                  </p>
                </div>

                <label
                  className={clsx(
                    "flex items-center justify-between gap-4 rounded-xl border border-border bg-card px-4 py-3",
                    spreadsheetCount === 0 && "opacity-60",
                  )}
                >
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">Process only the active sheet</p>
                    <p className="text-xs text-muted-foreground">Applies to Excel files in this upload.</p>
                  </div>
                  <span className="relative inline-flex items-center">
                    <input
                      type="checkbox"
                      className="peer sr-only"
                      checked={activeOnly}
                      disabled={spreadsheetCount === 0}
                      onChange={(event) => setActiveOnly(event.target.checked)}
                    />
                    <span className="h-5 w-9 rounded-full bg-muted transition peer-checked:bg-brand-600 peer-disabled:cursor-not-allowed" />
                    <span className="absolute left-0.5 h-4 w-4 rounded-full bg-white transition peer-checked:translate-x-4" />
                  </span>
                </label>

                {activeOnly ? (
                  <p className="text-xs text-muted-foreground">
                    Active sheet selection is resolved during processing.
                  </p>
                ) : null}
              </div>
            )}
          </section>
        </div>

        <footer className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">{processingNote}</p>
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={confirmDisabled}
              className="gap-2"
            >
              <UploadIcon className="h-4 w-4" />
              Upload {localFiles.length === 1 ? "file" : "files"}
            </Button>
          </div>
        </footer>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}

function isSpreadsheet(type: FileType) {
  return type === "xlsx" || type === "xls";
}

async function inspectWorkbookFile(file: File): Promise<{ names: string[]; activeName: string | null }> {
  const buffer = await file.arrayBuffer();
  const XLSX = await import("xlsx");
  const workbook = XLSX.read(buffer, { type: "array" });
  const names = workbook.SheetNames ?? [];
  const activeName = resolveActiveSheetName(workbook, names);
  return { names, activeName };
}

function resolveActiveSheetName(
  workbook: {
    SheetNames?: string[];
    Workbook?: { Views?: unknown[] };
  },
  names: string[],
) {
  const activeTab = (workbook.Workbook?.Views?.[0] as { activeTab?: number } | undefined)?.activeTab;
  if (typeof activeTab === "number" && activeTab >= 0 && activeTab < names.length) {
    return names[activeTab];
  }
  return names[0] ?? null;
}
