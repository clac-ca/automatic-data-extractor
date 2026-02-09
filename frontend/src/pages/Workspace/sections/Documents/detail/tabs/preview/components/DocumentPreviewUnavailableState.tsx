import { Button } from "@/components/ui/button";

export function DocumentPreviewUnavailableState({
  reason,
  onSwitchToOriginal,
}: {
  reason: string;
  onSwitchToOriginal: () => void;
}) {
  return (
    <div className="m-4 rounded-lg border border-border bg-background p-4 text-sm">
      <div className="font-medium text-foreground">Normalized preview unavailable</div>
      <div className="mt-1 text-muted-foreground">{reason}</div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-3"
        onClick={onSwitchToOriginal}
      >
        Switch to original preview
      </Button>
    </div>
  );
}
