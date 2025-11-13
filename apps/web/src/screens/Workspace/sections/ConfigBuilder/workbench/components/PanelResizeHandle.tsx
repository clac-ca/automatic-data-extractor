import type { PointerEventHandler } from "react";

interface PanelResizeHandleProps {
  readonly orientation: "horizontal" | "vertical";
  readonly onPointerDown: PointerEventHandler<HTMLDivElement>;
}

export function PanelResizeHandle({ orientation, onPointerDown }: PanelResizeHandleProps) {
  const isVertical = orientation === "vertical";
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={
        isVertical
          ? "w-1 cursor-col-resize select-none bg-transparent"
          : "h-1 cursor-row-resize select-none bg-transparent"
      }
      onPointerDown={onPointerDown}
    >
      <span className="sr-only">Resize panel</span>
    </div>
  );
}
