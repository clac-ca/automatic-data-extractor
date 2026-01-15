import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { DocumentsCommentsPanel } from "./DocumentsCommentsPanel";
import type { DocumentRow } from "../../types";

export function DocumentsCommentsPane({
  workspaceId,
  document,
  onClose,
  isLoading = false,
  errorMessage,
}: {
  workspaceId: string;
  document: DocumentRow | null;
  onClose: () => void;
  isLoading?: boolean;
  errorMessage?: string | null;
}) {
  const subtitle = document
    ? document.name
    : isLoading
      ? "Loading document..."
      : "Document unavailable";

  return (
    <section
      className="flex min-h-0 w-full flex-1 flex-col overflow-hidden border border-border bg-background shadow-sm"
      aria-label="Document comments"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/40 px-3 py-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-foreground">
            Comments
          </div>
          <div className="truncate text-xs text-muted-foreground">{subtitle}</div>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close comments" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {!document ? (
          isLoading ? (
            <div className="space-y-3 px-4 py-3">
              {[0, 1, 2].map((row) => (
                <div key={row} className="flex items-start gap-3">
                  <Skeleton className="h-9 w-9 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3 w-32" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center px-6 py-8 text-sm text-muted-foreground">
              {errorMessage ?? "We couldn’t load that document."}
            </div>
          )
        ) : (
          <DocumentsCommentsPanel workspaceId={workspaceId} document={document} />
        )}
      </div>
    </section>
  );
}
