import { type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { SpinnerIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";

export function DocumentsToolbar({
  configMissing,
  processingPaused,
  hasDocuments,
  isListFetching,
  hasListError,
  toolbarActions,
}: {
  configMissing: boolean;
  processingPaused: boolean;
  hasDocuments: boolean;
  isListFetching: boolean;
  hasListError: boolean;
  toolbarActions?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
      {configMissing ? (
        <Badge variant="secondary" className="text-xs">
          No active configuration
        </Badge>
      ) : null}
      {processingPaused ? (
        <Badge variant="secondary" className="text-xs">
          Processing paused
        </Badge>
      ) : null}
      {isListFetching ? (
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border/70 bg-muted/40">
          <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" />
        </span>
      ) : null}
      {!isListFetching && hasListError && hasDocuments ? (
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-destructive/30 bg-destructive/10">
          <AlertTriangle className="h-4 w-4 text-destructive" aria-label="Document list refresh failed" />
        </span>
      ) : null}
      {toolbarActions}
    </div>
  );
}
