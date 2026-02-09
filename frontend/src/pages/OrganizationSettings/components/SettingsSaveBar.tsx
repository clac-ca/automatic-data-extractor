import { Button } from "@/components/ui/button";

export function SettingsSaveBar({
  visible,
  canManage,
  isSaving,
  canSave,
  onSave,
  onDiscard,
  message = "You have unsaved changes.",
}: {
  readonly visible: boolean;
  readonly canManage: boolean;
  readonly isSaving: boolean;
  readonly canSave: boolean;
  readonly onSave: () => void;
  readonly onDiscard: () => void;
  readonly message?: string;
}) {
  if (!visible) {
    return null;
  }

  return (
    <div className="sticky bottom-3 z-20 mt-6 rounded-xl border border-border/80 bg-card/95 px-4 py-3 shadow-lg backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-foreground">{message}</p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!canManage || isSaving}
            onClick={onDiscard}
          >
            Discard
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={!canManage || isSaving || !canSave}
            onClick={onSave}
          >
            {isSaving ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </div>
    </div>
  );
}
