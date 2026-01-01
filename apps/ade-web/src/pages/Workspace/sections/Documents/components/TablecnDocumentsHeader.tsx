import type { ReactNode } from "react";

import { DocumentIcon } from "@components/icons";

export function TablecnDocumentsHeader({ actions }: { actions?: ReactNode }) {
  return (
    <header className="shrink-0 border-b border-border bg-gradient-to-b from-card via-card to-background/60 shadow-sm">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-background text-foreground shadow-sm">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-foreground">Documents</h1>
            <p className="text-xs text-muted-foreground">
              Track uploads, processing status, and mapping health.
            </p>
          </div>
        </div>
        {actions ? <div className="ml-auto flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>
    </header>
  );
}
