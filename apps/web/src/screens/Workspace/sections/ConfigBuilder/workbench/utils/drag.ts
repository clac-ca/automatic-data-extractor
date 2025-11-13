import type { PointerEvent as ReactPointerEvent } from "react";

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function trackPointerDrag(event: ReactPointerEvent, onMove: (moveEvent: PointerEvent) => void) {
  event.preventDefault();

  const handleMove = (moveEvent: PointerEvent) => {
    onMove(moveEvent);
  };

  const handleUp = () => {
    document.removeEventListener("pointermove", handleMove);
    document.removeEventListener("pointerup", handleUp);
  };

  document.addEventListener("pointermove", handleMove);
  document.addEventListener("pointerup", handleUp);
}
