import type { ReactNode } from "react";

import { Button } from "@components/tablecn/ui/button";
import { cn } from "@components/tablecn/lib/utils";

export function TablecnEmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-full flex-col items-center justify-center gap-3 rounded-md border border-border bg-card px-8 py-12 text-center text-sm",
        className,
      )}
    >
      <p className="font-semibold text-foreground">{title}</p>
      <p className="text-muted-foreground">{description}</p>
      {action ? (
        <Button size="sm" variant="outline" onClick={action.onClick}>
          {action.label}
        </Button>
      ) : null}
    </div>
  );
}

export function TablecnInlineBanner({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/30 px-4 py-3 text-sm",
        className,
      )}
    >
      <div>
        <p className="font-semibold text-foreground">{title}</p>
        <p className="text-muted-foreground">{description}</p>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}
