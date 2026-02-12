import { useId, useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { RunMetricsResource } from "@/pages/Workspace/sections/Documents/shared/types";

import { buildPreviewInlineStats, type PreviewCountSummary } from "../model";

const STAT_TONE_STYLES = {
  neutral: "border-border/70 bg-background text-foreground",
  success: "border-success/40 bg-success/10 text-success dark:bg-success/20",
  warning: "border-warning/50 bg-warning/15 text-warning-foreground",
  danger: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
} as const;

export function DocumentPreviewStatsRow({
  previewCountSummary,
  isCompactMode,
  onCompactModeChange,
  metrics,
}: {
  previewCountSummary: PreviewCountSummary | null;
  isCompactMode: boolean;
  onCompactModeChange: (enabled: boolean) => void;
  metrics: RunMetricsResource | null | undefined;
}) {
  const compactModeId = useId();
  const stats = useMemo(() => buildPreviewInlineStats(metrics), [metrics]);

  return (
    <div className="border-b border-border/80 bg-muted/20 px-4 py-2">
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <div className="inline-flex shrink-0 items-center gap-2 rounded-md border border-border/80 bg-background px-2 py-1">
          <Checkbox
            id={compactModeId}
            checked={isCompactMode}
            onCheckedChange={(checked) => onCompactModeChange(checked === true)}
          />
          <Label htmlFor={compactModeId} className="text-xs font-medium text-foreground">
            Hide empty rows and columns
          </Label>
        </div>
        {previewCountSummary ? (
          <>
            <Badge variant="outline" className="shrink-0 bg-background">
              {previewCountSummary.totalRowsLabel}
            </Badge>
            <Badge variant="outline" className="shrink-0 bg-background">
              {previewCountSummary.totalColumnsLabel}
            </Badge>
            {previewCountSummary.rowsVisibleLabel ? (
              <span className="shrink-0 rounded-md border border-border/70 bg-background px-2 py-0.5 text-xs text-muted-foreground">
                {previewCountSummary.rowsVisibleLabel}
              </span>
            ) : null}
            {previewCountSummary.columnsVisibleLabel ? (
              <span className="shrink-0 rounded-md border border-border/70 bg-background px-2 py-0.5 text-xs text-muted-foreground">
                {previewCountSummary.columnsVisibleLabel}
              </span>
            ) : null}
          </>
        ) : null}

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
    </div>
  );
}
