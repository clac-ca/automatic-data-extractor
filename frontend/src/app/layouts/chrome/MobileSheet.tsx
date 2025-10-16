import clsx from "clsx";
import type { ReactNode } from "react";

export interface MobileSheetProps {
  readonly side: "left" | "right";
  readonly open: boolean;
  readonly onClose: () => void;
  readonly children: ReactNode;
  readonly ariaLabel?: string;
}

export function MobileSheet({ side, open, onClose, children, ariaLabel }: MobileSheetProps) {
  return (
    <div className="md:hidden" aria-hidden={!open}>
      <div
        className={clsx(
          "fixed inset-0 z-40 bg-slate-900/40 transition-opacity duration-300",
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        className={clsx(
          "fixed inset-y-0 z-50 flex w-80 max-w-[90vw] flex-col bg-white shadow-xl transition-transform duration-300",
          side === "left" ? "left-0" : "right-0",
          open
            ? "translate-x-0"
            : side === "left"
              ? "-translate-x-full"
              : "translate-x-full",
        )}
      >
        {children}
      </div>
    </div>
  );
}
