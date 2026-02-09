import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";

export function DocumentPreviewHeader({
  name,
  source,
  onSourceChange,
  previewMeta,
}: {
  name: string;
  source: DocumentPreviewSource;
  onSourceChange: (source: DocumentPreviewSource) => void;
  previewMeta: {
    totalRows: number;
    totalColumns: number;
    truncatedRows?: boolean;
    truncatedColumns?: boolean;
  } | null;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background px-4 py-3">
      <div className="min-w-0">
        <div className="text-sm font-semibold">Preview</div>
        <div className="text-xs text-muted-foreground">{name}</div>
      </div>
      <div className="flex items-center gap-3">
        {previewMeta ? (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline" className="bg-background">
              {previewMeta.totalRows.toLocaleString()} rows
            </Badge>
            <Badge variant="outline" className="bg-background">
              {previewMeta.totalColumns.toLocaleString()} columns
            </Badge>
            {previewMeta.truncatedRows || previewMeta.truncatedColumns ? (
              <Badge variant="outline" className="bg-background">
                Preview truncated
              </Badge>
            ) : null}
          </div>
        ) : null}

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
  );
}
