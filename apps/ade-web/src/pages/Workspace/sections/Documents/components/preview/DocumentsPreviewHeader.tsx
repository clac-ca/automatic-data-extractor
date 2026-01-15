import { Maximize2, X } from "lucide-react";

import { Button } from "@/components/ui/button";

export function DocumentsPreviewHeader({
  title,
  subtitle,
  onClose,
  onExpand,
  actions,
}: {
  title: string;
  subtitle?: string | null;
  onClose: () => void;
  onExpand?: () => void;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/40 px-3 py-2">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-foreground">
          {title}
        </div>
        {subtitle ? (
          <div className="text-xs text-muted-foreground">{subtitle}</div>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {actions}
        {onExpand ? (
          <Button
            variant="ghost"
            size="icon"
            aria-label="Expand preview"
            onClick={onExpand}
          >
            <Maximize2 className="size-4" />
          </Button>
        ) : null}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close preview"
          onClick={onClose}
        >
          <X className="size-4" />
        </Button>
      </div>
    </div>
  );
}
