import { useId, useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { DocumentPreviewSource } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { RunMetricsResource } from "@/pages/Workspace/sections/Documents/shared/types";

import { buildPreviewInlineStats } from "../model";

const STAT_TONE_STYLES = {
  neutral: "border-border/70 bg-background text-foreground",
  success: "border-success/40 bg-success/10 text-success dark:bg-success/20",
  warning: "border-warning/50 bg-warning/15 text-warning-foreground",
  danger: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
} as const;

export function DocumentPreviewStatsRow({
  source,
  onSourceChange,
  showHiddenRowsAndColumns,
  onShowHiddenRowsAndColumnsChange,
  metrics,
}: {
  source: DocumentPreviewSource;
  onSourceChange: (source: DocumentPreviewSource) => void;
  showHiddenRowsAndColumns: boolean;
  onShowHiddenRowsAndColumnsChange: (enabled: boolean) => void;
  metrics: RunMetricsResource | null | undefined;
}) {
  const showHiddenId = useId();
  const stats = useMemo(() => buildPreviewInlineStats(metrics), [metrics]);

  return (
    <div className="bg-background px-4 py-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 overflow-x-auto">
          <div className="inline-flex h-8 shrink-0 items-center rounded-lg border border-border bg-muted/40 p-0.5">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className={cn(
                "h-7 rounded-md px-3 text-xs font-medium",
                source === "normalized"
                  ? "bg-background text-foreground shadow-sm hover:bg-background"
                  : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
              )}
              onClick={() => onSourceChange("normalized")}
            >
              Normalized
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className={cn(
                "h-7 rounded-md px-3 text-xs font-medium",
                source === "original"
                  ? "bg-background text-foreground shadow-sm hover:bg-background"
                  : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
              )}
              onClick={() => onSourceChange("original")}
            >
              Original
            </Button>
          </div>
          <div className="inline-flex shrink-0 items-center gap-2 px-2">
            <Checkbox
              id={showHiddenId}
              aria-label="Show hidden rows and columns"
              checked={showHiddenRowsAndColumns}
              onCheckedChange={(checked) => onShowHiddenRowsAndColumnsChange(checked === true)}
            />
            <Label htmlFor={showHiddenId} className="text-xs font-medium text-muted-foreground">
              Show hidden rows/columns
            </Label>
          </div>
        </div>
        {stats.length > 0 ? (
          <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
            {stats.map((stat) => (
              <Badge
                key={stat.id}
                variant="outline"
                className={cn("shrink-0 bg-background", STAT_TONE_STYLES[stat.tone])}
              >
                <span className="text-muted-foreground">{stat.label}:</span> {stat.value}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
