import { useLayoutEffect, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";

import { Dialog, DialogDescription, DialogHeader, DialogOverlay, DialogPortal, DialogTitle } from "@/components/ui/dialog";

import { DocumentsPreviewHeader } from "./DocumentsPreviewHeader";
import { DocumentsPreviewContent } from "./DocumentsPreviewContent";
import { DocumentsPreviewSkeleton } from "./DocumentsPreviewSkeleton";
import type { DocumentRow } from "../../types";

export function DocumentsPreviewDialog({
  open,
  onOpenChange,
  workspaceId,
  document: documentRow,
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
  const title = documentRow
    ? documentRow.name
    : isLoading
      ? "Loading document..."
      : "Document unavailable";
  const subtitle =
    documentRow
      ? documentRow.lastRun?.status
        ? `Last run: ${formatStatus(documentRow.lastRun.status)}`
        : "No runs yet"
      : undefined;

  const [portalContainer, setPortalContainer] = useState<HTMLElement | null>(() => {
    if (typeof window === "undefined") return null;
    return window.document.querySelector("[data-slot=\"workspace-content\"]");
  });

  useLayoutEffect(() => {
    if (portalContainer) return;
    const container = window.document.querySelector("[data-slot=\"workspace-content\"]");
    if (container instanceof HTMLElement) {
      setPortalContainer(container);
    }
  }, [portalContainer]);

  const handleClose = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {!open || portalContainer ? (
        <DialogPortal container={portalContainer ?? undefined}>
          <DialogOverlay className="absolute inset-0 z-[var(--app-z-modal)] bg-black/30" />
          <DialogPrimitive.Content
            aria-label="Document preview"
            className="absolute inset-0 z-[calc(var(--app-z-modal)+1)] flex h-full w-full flex-col overflow-hidden bg-background"
          >
            <DialogHeader className="sr-only">
              <DialogTitle>{title}</DialogTitle>
              {subtitle ? <DialogDescription>{subtitle}</DialogDescription> : null}
            </DialogHeader>
            <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
              <DocumentsPreviewHeader title={title} subtitle={subtitle} onClose={handleClose} />
              <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                {!documentRow ? (
                  isLoading ? (
                    <DocumentsPreviewSkeleton />
                  ) : (
                    <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
                      {errorMessage ?? "We couldn’t load that document."}
                    </div>
                  )
                ) : (
                  <DocumentsPreviewContent
                    workspaceId={workspaceId}
                    document={documentRow}
                    onDownloadOriginal={onDownloadOriginal}
                    onDownloadOutput={onDownloadOutput}
                  />
                )}
              </div>
            </section>
          </DialogPrimitive.Content>
        </DialogPortal>
      ) : null}
    </Dialog>
  );
}

function formatStatus(value: string) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}
