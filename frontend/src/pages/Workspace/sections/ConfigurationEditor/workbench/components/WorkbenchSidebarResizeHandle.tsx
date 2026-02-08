import { useSidebar } from "@/components/ui/sidebar";

import { clamp, trackPointerDrag } from "../utils/drag";

interface WorkbenchSidebarResizeHandleProps {
  readonly width: number;
  readonly minWidth: number;
  readonly maxWidth: number;
  readonly onResize: (width: number) => void;
}

export function WorkbenchSidebarResizeHandle({
  width,
  minWidth,
  maxWidth,
  onResize,
}: WorkbenchSidebarResizeHandleProps) {
  const { isMobile } = useSidebar();

  if (isMobile) {
    return null;
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
      aria-valuemin={minWidth}
      aria-valuemax={maxWidth}
      aria-valuenow={Math.round(width)}
      className="group relative hidden h-full w-2 cursor-col-resize select-none md:block"
      onPointerDown={(event) => {
        const startX = event.clientX;
        const startWidth = width;
        trackPointerDrag(event, {
          cursor: "col-resize",
          onMove: (moveEvent) => {
            const delta = moveEvent.clientX - startX;
            const nextWidth = clamp(startWidth + delta, minWidth, maxWidth);
            onResize(nextWidth);
          },
        });
      }}
    >
      <div className="absolute inset-y-0 left-1/2 w-px bg-border transition-colors group-hover:bg-ring/40" />
      <span className="sr-only">Resize sidebar</span>
    </div>
  );
}
