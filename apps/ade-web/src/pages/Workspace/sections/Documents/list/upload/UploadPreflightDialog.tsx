import { useEffect, useMemo, useState } from "react";

import type { UploadManagerQueueItem } from "./uploadManager";
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

  const confirmationDisabled = localFiles.length === 0;

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
    const items: UploadManagerQueueItem[] = localFiles.map((entry) => ({ file: entry.file }));
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

        <div className="mt-2 space-y-2">
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
