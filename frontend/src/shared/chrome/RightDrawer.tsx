import { createPortal } from "react-dom";
import { useEffect, useId, useRef, type ReactNode } from "react";

interface RightDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function RightDrawer({ open, onClose, title, description, children, footer }: RightDrawerProps) {
  const portalRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const lastFocusedElementRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  if (typeof document !== "undefined" && !portalRef.current) {
    portalRef.current = document.createElement("div");
    portalRef.current.dataset.rightDrawerRoot = "true";
  }

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    const node = portalRef.current;
    if (!node) {
      return;
    }

    document.body.appendChild(node);
    return () => {
      document.body.removeChild(node);
    };
  }, []);

  useEffect(() => {
    if (!open || typeof document === "undefined") {
      return;
    }

    lastFocusedElementRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const panel = panelRef.current;
    const focusTimeout = window.setTimeout(() => {
      panel?.focus();
    }, 0);

    return () => {
      window.clearTimeout(focusTimeout);
      const previouslyFocused = lastFocusedElementRef.current;
      lastFocusedElementRef.current = null;
      if (previouslyFocused) {
        previouslyFocused.focus();
      }
    };
  }, [open]);

  useEffect(() => {
    if (!open || typeof document === "undefined") {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open || typeof document === "undefined") {
      return;
    }

    const { body } = document;
    const previousOverflow = body.style.overflow;
    body.style.overflow = "hidden";
    return () => {
      body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!open || typeof document === "undefined" || !portalRef.current) {
    return null;
  }

  const labelledBy = titleId;
  const describedBy = description ? descriptionId : undefined;

  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <section
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        className="relative flex h-full w-full max-w-xl flex-col border-l border-slate-900 bg-slate-950 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-900 px-6 py-4">
          <div className="space-y-1">
            <h2 id={labelledBy} className="text-lg font-semibold text-slate-50">
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="text-sm text-slate-400">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-300 hover:border-slate-700"
          >
            Close
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-4 text-sm text-slate-200">{children}</div>
        {footer ? <footer className="border-t border-slate-900 px-6 py-4 text-sm text-slate-200">{footer}</footer> : null}
      </section>
    </div>,
    portalRef.current,
  );
}
