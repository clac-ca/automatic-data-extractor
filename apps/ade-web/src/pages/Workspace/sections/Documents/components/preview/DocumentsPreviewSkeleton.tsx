import { DataTableSkeleton } from "@/components/data-table/data-table-skeleton";

export function DocumentsPreviewSkeleton({
  columnCount = 6,
  rowCount = 8,
}: {
  columnCount?: number;
  rowCount?: number;
}) {
  return (
    <DataTableSkeleton
      columnCount={columnCount}
      rowCount={rowCount}
      withViewOptions={false}
      filterCount={0}
      className="min-h-[200px]"
    />
  );
}
