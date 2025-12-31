import clsx from "clsx";
import { createPortal } from "react-dom";
import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@components/ui/button";

type ConfirmDialogTone = "default" | "danger";

interface ConfirmDialogProps {
  readonly open: boolean;
  readonly title: string;
  readonly description?: string;
  readonly confirmLabel?: string;
  readonly cancelLabel?: string;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
  readonly isConfirming?: boolean;
  readonly children?: ReactNode;
  readonly confirmDisabled?: boolean;
  readonly tone?: ConfirmDialogTone;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  isConfirming,
  children,
  confirmDisabled,
  tone = "default",
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
      if (event.key === "Tab") {
        const root = dialogRef.current;
        if (!root) return;
        const focusable = Array.from(
          root.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
          ),
        ).filter((el) => !el.hasAttribute("disabled"));
        if (focusable.length === 0) return;
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
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel, open]);

  if (!open) {
    return null;
  }

  const toneStyles =
    tone === "danger"
      ? {
          badge: "bg-danger-500/15 text-danger-400",
          confirmVariant: "danger" as const,
        }
      : {
          badge: "bg-brand-500/10 text-brand-500",
          confirmVariant: "primary" as const,
        };

  return createPortal(
    <div className="fixed inset-0 z-50 px-4">
      <button
        type="button"
        className="absolute inset-0 bg-overlay/50"
        onClick={onCancel}
        aria-label="Close dialog"
      />
      <div className="relative flex min-h-full items-center justify-center">
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl"
          ref={dialogRef}
        >
          <div className="space-y-2">
            <p
              className={clsx(
                "inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.25em]",
                toneStyles.badge,
              )}
            >
              Confirm
            </p>
            <h3 className="text-xl font-semibold text-foreground">{title}</h3>
            {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
          </div>

          {children ? <div className="mt-4 space-y-3">{children}</div> : null}

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel} disabled={isConfirming}>
              {cancelLabel}
            </Button>
            <Button
              type="button"
              variant={toneStyles.confirmVariant}
              onClick={onConfirm}
              isLoading={isConfirming}
              disabled={confirmDisabled || isConfirming}
              className={tone === "danger" ? "hover:bg-danger-600" : undefined}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
