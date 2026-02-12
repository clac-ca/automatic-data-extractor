import { useEffect, useMemo, useState } from "react";

import type { UploadManagerQueueItem } from "./useUploadManager";
import {
  buildUploadRunOptions,
  supportsWorkbookSheetSelection,
} from "./sheetSelection";
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
import { CloseIcon, UploadIcon } from "@/components/icons";
import { cn } from "@/lib/utils";

import type { FileType } from "../../shared/types";
import { fileTypeLabel, formatBytes, inferFileType, stableId } from "../../shared/utils";

type UploadPreflightDialogProps = {
  readonly open: boolean;
  readonly files: File[];
  readonly onConfirm: (items: UploadManagerQueueItem[]) => void;
  readonly onCancel: () => void;
  readonly processingPaused: boolean;
  readonly configMissing: boolean;
};

type PreflightFile = {
  id: string;
  file: File;
  type: FileType;
};

export function UploadPreflightDialog({
  open,
  files,
  onConfirm,
  onCancel,
  processingPaused,
  configMissing,
}: UploadPreflightDialogProps) {
  const [localFiles, setLocalFiles] = useState<PreflightFile[]>([]);
  const [sheetScope, setSheetScope] = useState<"active" | "all">("active");

  useEffect(() => {
    if (!open) {
      setLocalFiles([]);
      setSheetScope("active");
      return;
    }
    setSheetScope("active");
    setLocalFiles(
      files.map((file) => ({
        id: stableId(),
        file,
        type: inferFileType(file.name, file.type),
      })),
    );
  }, [files, open]);

  const hasWorkbookUpload = useMemo(
    () => localFiles.some((entry) => supportsWorkbookSheetSelection(entry.type)),
    [localFiles],
  );
  const confirmationDisabled = localFiles.length === 0;
  const scopeAppliesLabel =
    localFiles.length <= 1 ? "Applies to this upload." : `Applies to all ${localFiles.length} queued files.`;

  const summaryLabel = useMemo(() => {
    if (localFiles.length === 0) return "No files selected";
    if (localFiles.length === 1) return localFiles[0].file.name;
    return `${localFiles.length} files selected`;
  }, [localFiles]);

  const removeFile = (id: string) => {
    setLocalFiles((prev) => prev.filter((entry) => entry.id !== id));
  };

  const handleConfirm = () => {
    if (!localFiles.length) return;
    const runOptions = buildUploadRunOptions(sheetScope, []);
    const items: UploadManagerQueueItem[] = localFiles.map((entry) => ({
      file: entry.file,
      runOptions,
    }));
    onConfirm(items);
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onCancel() : undefined)}>
      <DialogContent className="sm:max-w-[540px]">
        <DialogHeader>
          <DialogTitle>Upload documents</DialogTitle>
          <DialogDescription>
            {summaryLabel}
          </DialogDescription>
        </DialogHeader>

        {(processingPaused || configMissing) && (
          <Alert tone="warning" className="text-sm">
            {processingPaused
              ? "Processing is paused. Uploads will queue until processing resumes."
              : "No active configuration. Uploads will queue until a configuration is active."}
          </Alert>
        )}

        <div className="space-y-3 rounded-xl border border-border/80 bg-muted/20 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">Worksheet processing</p>
              <p className="text-xs text-muted-foreground">
                Choose how worksheets should be processed after upload.
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
                id="upload-sheet-scope-active"
                type="radio"
                name="upload-sheet-scope"
                className="mt-0.5 h-4 w-4"
                checked={sheetScope === "active"}
                onChange={() => setSheetScope("active")}
              />
              <span className="space-y-0.5">
                <label htmlFor="upload-sheet-scope-active" className="block font-medium text-foreground">
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
                id="upload-sheet-scope-all"
                type="radio"
                name="upload-sheet-scope"
                className="mt-0.5 h-4 w-4"
                checked={sheetScope === "all"}
                onChange={() => setSheetScope("all")}
              />
              <span className="space-y-0.5">
                <label htmlFor="upload-sheet-scope-all" className="block font-medium text-foreground">
                  All sheets
                </label>
                <span className="block text-xs text-muted-foreground">
                  Processes every worksheet in each workbook.
                </span>
              </span>
            </div>

          </div>

          {hasWorkbookUpload ? (
            <Alert tone="warning" className="text-xs">
              Worksheet-level selection is unavailable for direct uploads. Upload with Active sheet only or All sheets, then use reprocess for specific worksheets.
            </Alert>
          ) : null}
        </div>

        <div className="mt-2 max-h-64 space-y-2 overflow-y-auto pr-1">
          {localFiles.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-foreground">{entry.file.name}</p>
                <p className="text-[10px] text-muted-foreground">
                  {fileTypeLabel(entry.type)} · {formatBytes(entry.file.size)}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                onClick={() => removeFile(entry.id)}
                aria-label="Remove file"
              >
                <CloseIcon className="h-3 w-3" />
              </Button>
            </div>
          ))}
          {localFiles.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
              No files queued.
            </div>
          ) : null}
        </div>

        <DialogFooter className="mt-4 flex items-center justify-between sm:justify-between">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={confirmationDisabled} className="gap-2">
            <UploadIcon className="h-4 w-4" />
            Upload
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
