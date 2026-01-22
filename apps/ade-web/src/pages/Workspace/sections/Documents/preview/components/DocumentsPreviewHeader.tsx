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
    <div className="flex items-center gap-3 border-b bg-background/95 px-4 py-2">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-foreground">
          {title}
        </div>
        {subtitle ? (
          <div className="text-[11px] text-muted-foreground">{subtitle}</div>
        ) : null}
      </div>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Close preview"
        onClick={onClose}
        className="h-7 w-7"
      >
        <X className="size-4" />
      </Button>
    </div>
  );
}
