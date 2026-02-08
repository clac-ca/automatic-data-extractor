import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";

interface WorkbenchGuidedTourProps {
  readonly open: boolean;
  readonly onSkip: () => void;
  readonly onComplete: () => void;
}

interface TourStep {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly selector: string;
}

const TOUR_STEPS: readonly TourStep[] = [
  {
    id: "files",
    title: "File explorer",
    description: "Start in the file explorer to open config modules and move through your package quickly.",
    selector: '[data-guided-tour="files"]',
  },
  {
    id: "save",
    title: "Save behavior",
    description: "Save writes the active file. Unsaved files are auto-saved before validation, publish, and test run.",
    selector: '[data-guided-tour="save"]',
  },
  {
    id: "validation",
    title: "Validation flow",
    description: "Run validation to check the config package before you publish. Results stream in the console panel.",
    selector: '[data-guided-tour="validation"]',
  },
  {
    id: "publish",
    title: "Publish action",
    description: "Publish promotes this draft as active. Publishing is the only action that changes the active version.",
    selector: '[data-guided-tour="publish"]',
  },
  {
    id: "history",
    title: "Configuration menu",
    description:
      "Open the configuration title menu to rename, copy the configuration ID, or archive a draft when you’re done with it.",
    selector: '[data-guided-tour="history"]',
  },
];

interface PopoverPosition {
  readonly top: number;
  readonly left: number;
  readonly width: number;
}

const DEFAULT_WIDTH = 360;

export function WorkbenchGuidedTour({ open, onSkip, onComplete }: WorkbenchGuidedTourProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [position, setPosition] = useState<PopoverPosition>({
    top: 72,
    left: 24,
    width: DEFAULT_WIDTH,
  });
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      setStepIndex(0);
    }
  }, [open]);

  const step = TOUR_STEPS[stepIndex] ?? TOUR_STEPS[0];

  const recomputeLayout = useCallback(() => {
    if (!open || !step) {
      return;
    }
    const target = document.querySelector(step.selector) as HTMLElement | null;
    const rect = target?.getBoundingClientRect() ?? null;
    setTargetRect(rect);

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(DEFAULT_WIDTH, Math.max(280, viewportWidth - 32));
    const panelHeight = dialogRef.current?.offsetHeight ?? 260;

    if (!rect) {
      setPosition({
        top: Math.max(16, Math.round((viewportHeight - panelHeight) / 2)),
        left: Math.max(16, Math.round((viewportWidth - width) / 2)),
        width,
      });
      return;
    }

    let top = rect.bottom + 14;
    if (top + panelHeight > viewportHeight - 16) {
      top = rect.top - panelHeight - 14;
    }
    if (top < 16) {
      top = 16;
    }

    let left = rect.left;
    if (left + width > viewportWidth - 16) {
      left = viewportWidth - width - 16;
    }
    if (left < 16) {
      left = 16;
    }

    setPosition({ top: Math.round(top), left: Math.round(left), width });
  }, [open, step]);

  useEffect(() => {
    if (!open) {
      return;
    }
    recomputeLayout();
    window.addEventListener("resize", recomputeLayout);
    window.addEventListener("scroll", recomputeLayout, true);
    return () => {
      window.removeEventListener("resize", recomputeLayout);
      window.removeEventListener("scroll", recomputeLayout, true);
    };
  }, [open, recomputeLayout]);

  useEffect(() => {
    if (!open) {
      return;
    }
    recomputeLayout();
    const raf = window.requestAnimationFrame(() => recomputeLayout());
    return () => window.cancelAnimationFrame(raf);
  }, [open, stepIndex, recomputeLayout]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onSkip();
      }
      if (event.key !== "Tab") {
        return;
      }
      const root = dialogRef.current;
      if (!root) {
        return;
      }
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (focusable.length === 0) {
        return;
      }
      const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
      const nextIndex = event.shiftKey
        ? currentIndex <= 0
          ? focusable.length - 1
          : currentIndex - 1
        : currentIndex === focusable.length - 1
          ? 0
          : currentIndex + 1;
      focusable[nextIndex]?.focus();
      event.preventDefault();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onSkip, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();
  }, [open, stepIndex]);

  const highlightStyle = useMemo(() => {
    if (!targetRect) {
      return null;
    }
    return {
      top: Math.max(8, targetRect.top - 6),
      left: Math.max(8, targetRect.left - 6),
      width: Math.max(24, targetRect.width + 12),
      height: Math.max(24, targetRect.height + 12),
    };
  }, [targetRect]);

  if (!open) {
    return null;
  }

  const onNext = () => {
    if (stepIndex >= TOUR_STEPS.length - 1) {
      onComplete();
      return;
    }
    setStepIndex((current) => Math.min(current + 1, TOUR_STEPS.length - 1));
  };

  return createPortal(
    <div className="fixed inset-0 z-[var(--app-z-modal)]">
      <div className="absolute inset-0 bg-overlay-strong/90" />
      {highlightStyle ? (
        <div
          className="pointer-events-none fixed rounded-lg border-2 border-primary shadow-[0_0_0_9999px_rgba(0,0,0,0.42)] transition-all"
          style={highlightStyle}
        />
      ) : null}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Config builder guided tour"
        className="fixed rounded-xl border border-border bg-card p-4 shadow-2xl"
        style={{ top: position.top, left: position.left, width: position.width }}
      >
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Guided tour {stepIndex + 1}/{TOUR_STEPS.length}
          </p>
          <h3 className="text-base font-semibold text-foreground">{step.title}</h3>
          <p className="text-sm text-muted-foreground">{step.description}</p>
        </div>
        <div className="mt-4 flex items-center justify-between gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={onSkip}>
            Skip
          </Button>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={stepIndex === 0}
              onClick={() => setStepIndex((current) => Math.max(0, current - 1))}
            >
              Back
            </Button>
            <Button type="button" size="sm" onClick={onNext}>
              {stepIndex >= TOUR_STEPS.length - 1 ? "Done" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
