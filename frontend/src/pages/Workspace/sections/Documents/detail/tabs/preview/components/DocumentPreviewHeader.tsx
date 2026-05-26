import { Button } from "@/components/ui/button";
import { Loader2, Save } from "lucide-react";
import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";

export function DocumentPreviewHeader({
  name,
  source,
  onSourceChange,
  isDirty = false,
  isSaving = false,
  onSave,
}: {
  name: string;
  source: DocumentPreviewSource;
  onSourceChange: (source: DocumentPreviewSource) => void;
  isDirty?: boolean;
  isSaving?: boolean;
  onSave?: () => void;
}) {
  return (
    <div className="border-b border-border bg-background px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Preview</div>
          <div className="truncate text-xs text-muted-foreground" title={name}>
            {name}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isDirty && (
            <Button
              size="sm"
              variant="default"
              onClick={onSave}
              disabled={isSaving}
              className="h-8 gap-1.5 px-3 text-xs font-medium shadow-sm transition-all bg-emerald-600 hover:bg-emerald-500 text-white"
            >
              {isSaving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              {isSaving ? "Saving..." : "Save Changes"}
            </Button>
          )}
          <div className="inline-flex items-center rounded-lg border border-border bg-muted/20 p-0.5">
            <Button
              size="sm"
              variant={source === "normalized" ? "secondary" : "ghost"}
              onClick={() => onSourceChange("normalized")}
              className="h-8 px-3 text-xs"
            >
              Normalized
            </Button>
            <Button
              size="sm"
              variant={source === "original" ? "secondary" : "ghost"}
              onClick={() => onSourceChange("original")}
              className="h-8 px-3 text-xs"
            >
              Original
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

