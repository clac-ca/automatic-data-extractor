import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";

import { mapUiError } from "@/api/uiErrors";
import { AlertTriangleIcon, UploadIcon } from "@/components/icons";
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
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type ConfigurationImportDialogMode = "create" | "replace";
export type ConfigurationImportMethod = "zip" | "github";
export type ConfigurationImportSubmitPayload =
  | { readonly type: "zip"; readonly file: File }
  | { readonly type: "github"; readonly url: string };

interface ConfigurationImportDialogProps {
  readonly open: boolean;
  readonly mode: ConfigurationImportDialogMode;
  readonly isSubmitting: boolean;
  readonly canSubmit?: boolean;
  readonly disabledReason?: string | null;
  readonly hasUnsavedChanges?: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (payload: ConfigurationImportSubmitPayload) => Promise<void>;
  readonly onError?: (message: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${bytes} B`;
}

function isZipFile(file: File): boolean {
  return file.name.trim().toLowerCase().endsWith(".zip");
}

export function ConfigurationImportDialog({
  open,
  mode,
  isSubmitting,
  canSubmit = true,
  disabledReason = null,
  hasUnsavedChanges = false,
  onClose,
  onSubmit,
  onError,
}: ConfigurationImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [method, setMethod] = useState<ConfigurationImportMethod>("zip");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    setMethod("zip");
    setSelectedFile(null);
    setGithubUrl("");
    setInlineError(null);
    setDragActive(false);
  }, [open]);

  const fallbackError =
    mode === "replace"
      ? "Unable to replace configuration."
      : "Unable to import configuration.";
  const submitLabel = mode === "replace" ? "Replace configuration" : "Import configuration";
  const title = mode === "replace" ? "Replace configuration" : "Import configuration";
  const description =
    mode === "replace"
      ? "Choose a zip file or public GitHub repository URL to replace this draft configuration."
      : "Choose a zip file or public GitHub repository URL to create a new draft configuration.";

  const setFile = useCallback((file: File | null) => {
    if (!file) {
      return;
    }
    if (!isZipFile(file)) {
      setSelectedFile(null);
      setInlineError("Please choose a .zip archive.");
      return;
    }
    setSelectedFile(file);
    setInlineError(null);
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      event.target.value = "";
      setFile(file);
    },
    [setFile],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.stopPropagation();
      setDragActive(false);
      const file = event.dataTransfer.files?.[0] ?? null;
      setFile(file);
    },
    [setFile],
  );

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) {
      setInlineError(disabledReason || "Import is currently unavailable.");
      return;
    }
    try {
      if (method === "zip") {
        if (!selectedFile) {
          setInlineError("Choose a .zip file to continue.");
          return;
        }
        await onSubmit({ type: "zip", file: selectedFile });
        return;
      }

      const trimmedUrl = githubUrl.trim();
      if (!trimmedUrl) {
        setInlineError("Enter a GitHub repository URL to continue.");
        return;
      }
      await onSubmit({ type: "github", url: trimmedUrl });
    } catch (error) {
      const mapped = mapUiError(error, { fallback: fallbackError });
      setInlineError(mapped.message);
      onError?.(mapped.message);
    }
  }, [
    canSubmit,
    disabledReason,
    fallbackError,
    githubUrl,
    method,
    onError,
    onSubmit,
    selectedFile,
  ]);

  const isReadyToSubmit =
    method === "zip" ? Boolean(selectedFile) : githubUrl.trim().length > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isSubmitting) {
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-xl" showCloseButton={!isSubmitting}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant={method === "zip" ? "default" : "outline"}
              onClick={() => {
                setMethod("zip");
                setInlineError(null);
              }}
              disabled={isSubmitting}
            >
              ZIP file
            </Button>
            <Button
              type="button"
              variant={method === "github" ? "default" : "outline"}
              onClick={() => {
                setMethod("github");
                setInlineError(null);
              }}
              disabled={isSubmitting}
            >
              GitHub URL
            </Button>
          </div>

          {method === "zip" ? (
            <div
              data-testid="config-import-dropzone"
              className={cn(
                "rounded-xl border border-dashed p-6 text-center transition-colors",
                dragActive ? "border-primary bg-primary/5" : "border-border bg-muted/20",
              )}
              onDragEnter={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setDragActive(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setDragActive(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                event.stopPropagation();
                if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
                  return;
                }
                setDragActive(false);
              }}
              onDrop={handleDrop}
            >
              <UploadIcon className="mx-auto h-8 w-8 text-primary" />
              <p className="mt-2 text-sm font-semibold text-foreground">Drag and drop a .zip file</p>
              <p className="mt-1 text-xs text-muted-foreground">or browse from your computer</p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-3"
                disabled={isSubmitting}
                onClick={() => fileInputRef.current?.click()}
              >
                Browse zip
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip,application/zip"
                className="hidden"
                onChange={handleFileInputChange}
              />
            </div>
          ) : (
            <div className="space-y-2 rounded-xl border border-border bg-muted/20 p-4">
              <label className="text-xs font-medium text-foreground" htmlFor="config-github-import-url">
                GitHub repository URL
              </label>
              <Input
                id="config-github-import-url"
                placeholder="https://github.com/OWNER/REPO or /tree/BRANCH"
                value={githubUrl}
                disabled={isSubmitting}
                onChange={(event) => {
                  setGithubUrl(event.target.value);
                  setInlineError(null);
                }}
              />
              <p className="text-xs text-muted-foreground">
                Private repositories are not supported. Use GitHub Download ZIP, then import the ZIP
                file here. Public repository and GitHub ZIP links are supported.
              </p>
            </div>
          )}

          {method === "zip" && selectedFile ? (
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="truncate text-sm font-medium text-foreground">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">{formatBytes(selectedFile.size)}</p>
            </div>
          ) : null}

          <div className="rounded-lg border border-border/80 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            Supports direct exports and GitHub-generated nested wrapper zip archives.
          </div>

          {mode === "replace" && hasUnsavedChanges ? (
            <Alert tone="warning" icon={<AlertTriangleIcon className="h-4 w-4" />}>
              You have unsaved changes in the editor. Import will replace configuration files.
            </Alert>
          ) : null}

          {!canSubmit && disabledReason ? (
            <Alert tone="warning">{disabledReason}</Alert>
          ) : null}

          {inlineError ? <Alert tone="danger">{inlineError}</Alert> : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => {
              void handleSubmit();
            }}
            disabled={isSubmitting || !canSubmit || !isReadyToSubmit}
            isLoading={isSubmitting}
          >
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
