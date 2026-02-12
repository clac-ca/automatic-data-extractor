import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

export function SettingsStickyActionBar({
  visible,
  isSaving,
  canSave = true,
  disabledReason,
  saveLabel = "Save changes",
  discardLabel = "Discard",
  message = "Unsaved changes",
  onSave,
  onDiscard,
  extra,
}: {
  readonly visible: boolean;
  readonly isSaving?: boolean;
  readonly canSave?: boolean;
  readonly disabledReason?: string;
  readonly saveLabel?: string;
  readonly discardLabel?: string;
  readonly message?: string;
  readonly onSave: () => void;
  readonly onDiscard: () => void;
  readonly extra?: ReactNode;
}) {
  if (!visible) {
    return null;
  }

  return (
    <div className="sticky bottom-0 z-30 mt-8 rounded-xl border border-border/70 bg-background/95 p-3 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-background/85">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{message}</p>
          {disabledReason && !isSaving && !canSave ? (
            <p className="text-xs text-destructive">{disabledReason}</p>
          ) : null}
        </div>
        <div className="flex w-full flex-wrap items-center justify-end gap-2 sm:w-auto">
          {extra}
          <Button type="button" variant="ghost" size="sm" onClick={onDiscard} disabled={isSaving}>
            {discardLabel}
          </Button>
          <Button type="button" size="sm" onClick={onSave} disabled={isSaving || !canSave}>
            {isSaving ? "Saving..." : saveLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
