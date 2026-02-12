import { cn } from "@/lib/utils";

import type { PreviewSheet } from "../hooks/useDocumentPreviewModel";

function buildSheetLabel(sheet: PreviewSheet) {
  return sheet.name || `Sheet ${sheet.index + 1}`;
}

export function DocumentPreviewSheetTabs({
  sheets,
  selectedSheetName,
  isLoading,
  onSheetSelect,
}: {
  sheets: PreviewSheet[];
  selectedSheetName: string | null;
  isLoading: boolean;
  onSheetSelect: (sheetName: string) => void;
}) {
  return (
    <div className="sticky bottom-0 z-20 border-t border-border bg-background/95 px-3 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/90">
      {sheets.length > 0 ? (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {sheets.map((sheet) => {
            const isActive = sheet.name === selectedSheetName;

            return (
              <button
                key={`${sheet.index}:${sheet.name}`}
                type="button"
                className={cn(
                  "rounded-md border px-3 py-1.5 text-xs whitespace-nowrap",
                  isActive
                    ? "border-border bg-background text-foreground shadow-sm"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
                onClick={() => onSheetSelect(sheet.name)}
              >
                {buildSheetLabel(sheet)}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">{isLoading ? "Loading sheets..." : "No sheets available."}</div>
      )}
    </div>
  );
}
