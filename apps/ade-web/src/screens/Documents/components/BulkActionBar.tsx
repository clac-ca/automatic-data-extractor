import { Button } from "@ui/Button";

export function BulkActionBar({
  count,
  outputReadyCount,
  onClear,
  onAddTag,
  onDownloadOriginals,
  onDownloadOutputs,
}: {
  count: number;
  outputReadyCount: number;
  onClear: () => void;
  onAddTag: () => void;
  onDownloadOriginals: () => void;
  onDownloadOutputs: () => void;
}) {
  if (count <= 0) return null;

  return (
    <div className="sticky bottom-0 z-10 shrink-0 border-t border-border bg-card px-6 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-foreground">
          <span className="font-semibold">{count}</span> selected
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" type="button" variant="secondary" onClick={onAddTag}>
            Add tags
          </Button>
          <div className="flex items-center gap-2">
            <Button size="sm" type="button" variant="secondary" onClick={onDownloadOutputs}>
              Download outputs
            </Button>
            <span className="text-[11px] font-semibold text-muted-foreground">
              {outputReadyCount}/{count} ready
            </span>
          </div>
          <Button size="sm" type="button" variant="secondary" onClick={onDownloadOriginals}>
            Download originals
          </Button>
          <Button size="sm" type="button" variant="ghost" onClick={onClear}>
            Clear
          </Button>
        </div>
      </div>
    </div>
  );
}
