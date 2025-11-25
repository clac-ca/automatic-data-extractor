import type { PointerEvent as ReactPointerEvent } from "react";

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

interface PointerDragOptions {
  readonly onMove: (moveEvent: PointerEvent) => void;
  readonly onEnd?: (moveEvent: PointerEvent) => void;
  readonly cursor?: "col-resize" | "row-resize";
}

export function trackPointerDrag(event: ReactPointerEvent, options: PointerDragOptions) {
  const { onMove, onEnd, cursor } = options;

  if (typeof window === "undefined") {
    return;
  }

  event.preventDefault();

  const pointerId = event.pointerId;
  const target = event.currentTarget as HTMLElement;
  const previousCursor = document.body.style.cursor;
  const previousUserSelect = document.body.style.userSelect;
  let animationFrame: number | null = null;
  let lastMoveEvent: PointerEvent | null = null;
  let active = true;

  const cleanup = (finalEvent: PointerEvent) => {
    if (!active) {
      return;
    }
    active = false;
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    document.body.style.cursor = previousCursor;
    document.body.style.userSelect = previousUserSelect;
    window.removeEventListener("pointermove", handleMove);
    window.removeEventListener("pointerup", handleUpOrCancel);
    window.removeEventListener("pointercancel", handleUpOrCancel);
    target.removeEventListener("lostpointercapture", handleLostCapture);
    if (target.hasPointerCapture?.(pointerId)) {
      try {
        target.releasePointerCapture(pointerId);
      } catch {
        // ignore release failures caused by stale handles
      }
    }
    if (onEnd) {
      onEnd(finalEvent);
    }
  };

  const handleMove = (moveEvent: PointerEvent) => {
    if (!active || moveEvent.pointerId !== pointerId) {
      return;
    }
    lastMoveEvent = moveEvent;
    if (animationFrame !== null) {
      return;
    }
    animationFrame = window.requestAnimationFrame(() => {
      animationFrame = null;
      if (lastMoveEvent) {
        onMove(lastMoveEvent);
      }
    });
  };

  const handleUpOrCancel = (pointerEvent: PointerEvent) => {
    if (pointerEvent.pointerId !== pointerId) {
      return;
    }
    cleanup(pointerEvent);
  };

  const handleLostCapture = (pointerEvent: PointerEvent) => {
    if (pointerEvent.pointerId !== pointerId) {
      return;
    }
    cleanup(pointerEvent);
  };

  if (cursor) {
    document.body.style.cursor = cursor;
  }
  document.body.style.userSelect = "none";

  try {
    target.setPointerCapture(pointerId);
  } catch {
    // Pointer capture is not critical; ignore failures (e.g., when ref is gone)
  }

  window.addEventListener("pointermove", handleMove);
  window.addEventListener("pointerup", handleUpOrCancel);
  window.addEventListener("pointercancel", handleUpOrCancel);
  target.addEventListener("lostpointercapture", handleLostCapture);
}
