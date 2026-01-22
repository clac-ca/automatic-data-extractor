import {
  DataGridSkeleton,
  DataGridSkeletonGrid,
  DataGridSkeletonToolbar,
} from "@/components/data-grid/data-grid-skeleton";

export function DocumentsPreviewSkeleton({
  columnCount = 6,
  rowCount = 8,
}: {
  columnCount?: number;
  rowCount?: number;
}) {
  const actionCount = Math.min(5, Math.max(2, Math.round(columnCount / 3)));
  const gridMinHeight = Math.min(480, Math.max(200, rowCount * 32));

  return (
    <DataGridSkeleton className="min-h-[200px]">
      <DataGridSkeletonToolbar actionCount={actionCount} />
      <DataGridSkeletonGrid style={{ minHeight: gridMinHeight }} />
    </DataGridSkeleton>
  );
}
