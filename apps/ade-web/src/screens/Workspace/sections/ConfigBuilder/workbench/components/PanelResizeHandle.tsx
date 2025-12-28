import clsx from "clsx";
import type { PointerEventHandler } from "react";

interface PanelResizeHandleProps {
  readonly orientation: "horizontal" | "vertical";
  readonly onPointerDown: PointerEventHandler<HTMLDivElement>;
  readonly onDoubleClick?: PointerEventHandler<HTMLDivElement>;
  readonly onToggle?: () => void;
  readonly collapsed?: boolean;
}

export function PanelResizeHandle({
  orientation,
  onPointerDown,
  onDoubleClick,
  onToggle,
  collapsed,
}: PanelResizeHandleProps) {
  const isVertical = orientation === "vertical";
  const chevron = isVertical ? "⋮" : collapsed ? "▴" : "▾";

  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={clsx(
        "relative select-none bg-transparent group",
        isVertical ? "w-4 cursor-col-resize" : "h-3 cursor-row-resize",
      )}
      style={{ touchAction: "none" }}
      onPointerDown={onPointerDown}
      onDoubleClick={onDoubleClick}
      title={isVertical ? "Drag to resize" : "Drag to resize · Double-click to hide/show console"}
    >
      <span className="sr-only">Resize panel</span>
      <div
        className={clsx(
          "absolute inset-0 flex items-center justify-center",
          isVertical ? "px-[6px]" : "py-[6px]",
        )}
        aria-hidden
      >
        <div className={clsx(isVertical ? "h-full w-px" : "h-px w-full", "bg-muted-foreground/50")} />
      </div>
      {onToggle && !isVertical ? (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onToggle();
          }}
          className="absolute right-1/2 top-1/2 h-5 w-5 -translate-y-1/2 translate-x-[40%] rounded bg-foreground/70 text-[10px] text-background opacity-0 shadow-sm transition-opacity group-hover:opacity-100 focus:opacity-100 focus:outline-none"
          aria-label={collapsed ? "Show console" : "Hide console"}
          title={collapsed ? "Show console" : "Hide console"}
        >
          {chevron}
        </button>
      ) : null}
    </div>
  );
}
