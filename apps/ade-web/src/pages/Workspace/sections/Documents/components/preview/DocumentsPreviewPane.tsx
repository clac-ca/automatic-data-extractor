import { useEffect } from "react";

import { DocumentsPreviewHeader } from "./DocumentsPreviewHeader";
import { DocumentsPreviewTable } from "./DocumentsPreviewTable";
import { DocumentsPreviewSkeleton } from "./DocumentsPreviewSkeleton";
import type { DocumentRow } from "../../types";

export function DocumentsPreviewPane({
  workspaceId,
  document,
  onClose,
  onDownloadOriginal,
  onDownloadOutput,
  isLoading = false,
  errorMessage,
}: {
  workspaceId: string;
  document: DocumentRow | null;
  onClose: () => void;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onDownloadOutput?: (document: DocumentRow) => void;
  isLoading?: boolean;
  errorMessage?: string | null;
}) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

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

  return (
    <section
      className="flex min-h-0 w-full flex-1 flex-col overflow-hidden border border-border bg-background shadow-sm"
      aria-label="Document preview"
    >
      <DocumentsPreviewHeader
        title={title}
        subtitle={subtitle}
        onClose={onClose}
      />
      <div className="min-h-0 flex-1 overflow-hidden">
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
  );
}

function formatStatus(value: string) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}
