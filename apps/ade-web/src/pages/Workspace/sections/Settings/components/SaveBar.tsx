import type { ReactNode } from "react";

import { Button } from "@components/Button";

interface SaveBarProps {
  readonly isDirty: boolean;
  readonly isSaving?: boolean;
  readonly onCancel?: () => void;
  readonly onSave: () => void;
  readonly saveLabel?: string;
  readonly cancelLabel?: string;
  readonly children?: ReactNode;
}

export function SaveBar({
  isDirty,
  isSaving,
  onCancel,
  onSave,
  saveLabel = "Save changes",
  cancelLabel = "Discard",
  children,
}: SaveBarProps) {
  if (!isDirty && !children) {
    return null;
  }

  return (
    <div className="sticky bottom-0 left-0 right-0 mt-4 rounded-b-2xl border border-t bg-card/95 p-4 shadow-[0_-8px_20px_-12px_rgb(var(--sys-color-shadow)/0.25)] backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-muted-foreground">{children}</div>
        <div className="flex flex-wrap items-center gap-2">
          {onCancel ? (
            <Button type="button" variant="ghost" onClick={onCancel} disabled={isSaving || !isDirty}>
              {cancelLabel}
            </Button>
          ) : null}
          <Button type="button" onClick={onSave} isLoading={isSaving} disabled={!isDirty || isSaving}>
            {saveLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
