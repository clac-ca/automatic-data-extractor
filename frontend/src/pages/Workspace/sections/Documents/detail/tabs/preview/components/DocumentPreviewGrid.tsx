import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export function DocumentPreviewGrid({
  hasSheetError,
  hasPreviewError,
  isLoading,
  hasSheets,
  hasData,
  rows,
  columnLabels,
}: {
  hasSheetError: boolean;
  hasPreviewError: boolean;
  isLoading: boolean;
  hasSheets: boolean;
  hasData: boolean;
  rows: unknown[][];
  columnLabels: string[];
}) {
  if (hasSheetError || hasPreviewError) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        Unable to load preview data. Refresh the page or try again later.
      </div>
    );
  }

  if (isLoading) {
    return <LoadingState />;
  }

  if (!hasSheets) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        No sheets available for this source.
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
        Select a sheet to view a preview.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-background">
      <Table className="min-w-[720px]">
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 z-20 w-12 bg-muted/50 text-center">#</TableHead>
            {columnLabels.map((label, index) => (
              <TableHead key={`${label}-${index}`} className="min-w-24 bg-muted/30 text-center font-mono text-xs">
                {label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={Math.max(columnLabels.length + 1, 1)} className="text-sm text-muted-foreground">
                No rows available in the preview.
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row, rowIndex) => {
              const cells = Array.isArray(row) ? row : [];

              return (
                <TableRow key={`row-${rowIndex}`}>
                  <TableCell className="sticky left-0 z-10 w-12 bg-muted/40 text-center font-mono text-xs text-muted-foreground">
                    {rowIndex + 1}
                  </TableCell>
                  {columnLabels.map((_, colIndex) => (
                    <TableCell
                      key={`cell-${rowIndex}-${colIndex}`}
                      className={cn("max-w-64 truncate")}
                      title={renderPreviewCell(cells[colIndex])}
                    >
                      {renderPreviewCell(cells[colIndex])}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="flex gap-3">
          <Skeleton className="h-6 w-12" />
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-24" />
        </div>
      ))}
    </div>
  );
}

function renderPreviewCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (
    typeof value === "number"
    || typeof value === "boolean"
    || typeof value === "bigint"
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
