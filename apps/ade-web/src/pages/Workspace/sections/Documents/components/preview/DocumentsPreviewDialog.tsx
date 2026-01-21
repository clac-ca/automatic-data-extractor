import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";

import { DocumentsPreviewHeader } from "./DocumentsPreviewHeader";
import { DocumentsPreviewTable } from "./DocumentsPreviewTable";
import { DocumentsPreviewSkeleton } from "./DocumentsPreviewSkeleton";
import type { DocumentRow } from "../../types";

export function DocumentsPreviewDialog({
  open,
  onOpenChange,
  workspaceId,
  document,
  onDownloadOriginal,
  onDownloadOutput,
  isLoading = false,
  errorMessage,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaceId: string;
  document: DocumentRow | null;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onDownloadOutput?: (document: DocumentRow) => void;
  isLoading?: boolean;
  errorMessage?: string | null;
}) {
  const title = document
    ? document.name
    : isLoading
      ? "Loading document..."
      : "Document unavailable";
  const subtitle =
    document
      ? document.lastRun?.status
        ? `Last run: ${formatStatus(document.lastRun.status)}`
        : "No runs yet"
      : undefined;

  const handleClose = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="left-4 top-4 flex h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden p-0 sm:max-w-none"
      >
        <DialogHeader className="sr-only">
          <DialogTitle>{title}</DialogTitle>
          {subtitle ? <DialogDescription>{subtitle}</DialogDescription> : null}
        </DialogHeader>
        <section
          className="flex min-h-0 min-w-0 h-full w-full flex-1 flex-col overflow-hidden bg-background"
          aria-label="Document preview"
        >
          <DocumentsPreviewHeader title={title} subtitle={subtitle} onClose={handleClose} />
          <Separator />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            {!document ? (
              isLoading ? (
                <DocumentsPreviewSkeleton />
              ) : (
                <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
                  {errorMessage ?? "We couldn’t load that document."}
                </div>
              )
            ) : (
              <DocumentsPreviewTable
                workspaceId={workspaceId}
                document={document}
                onDownloadOriginal={onDownloadOriginal}
                onDownloadOutput={onDownloadOutput}
              />
            )}
          </div>
        </section>
      </DialogContent>
    </Dialog>
  );
}

function formatStatus(value: string) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}
