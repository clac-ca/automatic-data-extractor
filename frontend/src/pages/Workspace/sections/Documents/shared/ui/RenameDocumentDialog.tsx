import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

type DocumentNameParts = {
  baseName: string;
  extension: string;
};

function splitDocumentName(name: string): DocumentNameParts {
  const index = name.lastIndexOf(".");
  if (index <= 0) {
    return { baseName: name, extension: "" };
  }
  return {
    baseName: name.slice(0, index),
    extension: name.slice(index),
  };
}

export function RenameDocumentDialog({
  open,
  documentName,
  isPending = false,
  errorMessage = null,
  onOpenChange,
  onSubmit,
  onClearError,
}: {
  open: boolean;
  documentName: string;
  isPending?: boolean;
  errorMessage?: string | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (nextName: string) => Promise<void> | void;
  onClearError?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { baseName, extension } = useMemo(
    () => splitDocumentName(documentName),
    [documentName],
  );
  const [draftBaseName, setDraftBaseName] = useState(baseName);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraftBaseName(baseName);
    setLocalError(null);
  }, [baseName, open]);

  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
    return () => cancelAnimationFrame(frame);
  }, [open]);

  const handleSubmit = async () => {
    const normalizedBase = draftBaseName.trim();
    if (!normalizedBase) {
      setLocalError("Document name cannot be blank.");
      return;
    }
    await onSubmit(extension ? `${normalizedBase}${extension}` : normalizedBase);
  };

  const message = localError ?? errorMessage;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rename document</DialogTitle>
          <DialogDescription>
            Update the file name while keeping the existing extension.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label htmlFor="rename-document-input" className="text-sm font-medium">
            Name
          </label>
          <div className="flex items-center">
            <Input
              id="rename-document-input"
              ref={inputRef}
              value={draftBaseName}
              onChange={(event) => {
                setDraftBaseName(event.target.value);
                if (localError) setLocalError(null);
                onClearError?.();
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleSubmit();
                }
                if (event.key === "Escape") {
                  event.preventDefault();
                  onOpenChange(false);
                }
              }}
              className={extension ? "rounded-r-none border-r-0" : undefined}
              disabled={isPending}
              autoComplete="off"
            />
            {extension ? (
              <div className="inline-flex h-9 items-center rounded-r-md border border-input bg-muted/40 px-3 text-sm text-muted-foreground">
                {extension}
              </div>
            ) : null}
          </div>
          {message ? <p className="text-sm text-destructive">{message}</p> : null}
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button type="button" onClick={() => void handleSubmit()} disabled={isPending}>
            {isPending ? "Renaming..." : "Rename"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { splitDocumentName };
