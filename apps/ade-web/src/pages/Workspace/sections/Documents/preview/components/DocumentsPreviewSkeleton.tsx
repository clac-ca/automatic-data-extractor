import { Skeleton } from "@/components/ui/skeleton";

export function DocumentsPreviewSkeleton({
  columnCount = 6,
  rowCount = 8,
}: {
  columnCount?: number;
  rowCount?: number;
}) {
  const safeColumnCount = Math.min(10, Math.max(3, columnCount));
  const safeRowCount = Math.min(12, Math.max(4, rowCount));
  const actionCount = Math.min(5, Math.max(2, Math.round(safeColumnCount / 2)));
  const gridMinHeight = Math.min(480, Math.max(200, safeRowCount * 32));
  const gridTemplateColumns = `repeat(${safeColumnCount}, minmax(0, 1fr))`;
  const cellCount = safeColumnCount * safeRowCount;

  return (
    <div className="flex min-h-[200px] flex-col gap-3">
      <div className="flex justify-end gap-2">
        {Array.from({ length: actionCount }, (_, index) => (
          <Skeleton key={`action-${index}`} className="h-8 w-10" />
        ))}
      </div>
      <div className="overflow-hidden rounded-md border border-border/50">
        <div
          className="grid gap-px bg-border/50"
          style={{ gridTemplateColumns }}
        >
          {Array.from({ length: safeColumnCount }, (_, index) => (
            <Skeleton key={`header-${index}`} className="h-8 rounded-none" />
          ))}
        </div>
        <div
          className="grid gap-px bg-border/50"
          style={{ gridTemplateColumns, minHeight: gridMinHeight }}
        >
          {Array.from({ length: cellCount }, (_, index) => (
            <Skeleton key={`cell-${index}`} className="h-8 rounded-none" />
          ))}
        </div>
      </div>
    </div>
  );
}
