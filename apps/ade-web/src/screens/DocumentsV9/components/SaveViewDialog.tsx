import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

export function SaveViewDialog({
  open,
  initialName,
  onCancel,
  onSave,
}: {
  open: boolean;
  initialName: string;
  onCancel: () => void;
  onSave: (name: string) => void;
}) {
  const [name, setName] = useState(initialName);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const inputId = useId();

  useEffect(() => {
    if (open) setName(initialName);
  }, [initialName, open]);

  useEffect(() => {
    if (!open) return;
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

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 px-4">
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/40"
        onClick={onCancel}
        aria-label="Close dialog"
      />
      <div className="relative flex min-h-full items-center justify-center">
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
          className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl"
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSave(name.trim() || "Untitled view");
            }}
          >
            <h3 id={titleId} className="text-sm font-semibold text-slate-900">
              Save view
            </h3>
            <p id={descriptionId} className="mt-1 text-sm text-slate-500">
              Save the current search + filters so you can return to it quickly.
            </p>

            <div className="mt-4">
              <label htmlFor={inputId} className="text-xs font-semibold text-slate-500">
                View name
              </label>
              <Input
                id={inputId}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Failed PDFs (Vendor ABC)"
                className="mt-1"
                autoFocus
              />
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={onCancel}>
                Cancel
              </Button>
              <Button type="submit">Save</Button>
            </div>
          </form>
        </div>
      </div>
    </div>,
    document.body,
  );
}
