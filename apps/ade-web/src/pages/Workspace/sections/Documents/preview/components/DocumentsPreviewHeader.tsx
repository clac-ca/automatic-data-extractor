import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

export function DocumentsPreviewHeader({
  title,
  subtitle,
  onClose,
}: {
  title: string;
  subtitle?: string | null;
  onClose: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 bg-muted/40 px-6 py-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-foreground">
          {title}
        </div>
        {subtitle ? (
          <div className="text-xs text-muted-foreground">{subtitle}</div>
        ) : null}
      </div>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Close preview"
        onClick={onClose}
      >
        <X className="size-4" />
      </Button>
    </div>
  );
}
