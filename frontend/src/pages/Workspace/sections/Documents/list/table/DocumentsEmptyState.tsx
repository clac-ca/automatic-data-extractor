import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function DocumentsEmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void } | ReactNode;
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
        typeof action === "object" && "label" in action ? (
          <Button size="sm" variant="outline" onClick={action.onClick}>
            {action.label}
          </Button>
        ) : (
          action
        )
      ) : null}
    </div>
  );
}
