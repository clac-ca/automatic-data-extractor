import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import clsx from "clsx";

export interface ProfileDropdownAction {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly onSelect: () => void;
  readonly icon?: ReactNode;
}

export interface ProfileDropdownProps {
  readonly displayName: string;
  readonly email: string;
  readonly actions?: readonly ProfileDropdownAction[];
  readonly onSignOut: () => void;
  readonly signingOut?: boolean;
}

export function ProfileDropdown({
  displayName,
  email,
  actions = [],
  onSignOut,
  signingOut = false,
}: ProfileDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const initials = useMemo(() => deriveInitials(displayName || email), [displayName, email]);

  return (
    <div
      ref={containerRef}
      className="relative"
      onBlur={(event) => {
        if (!containerRef.current) {
          return;
        }
        if (!containerRef.current.contains(event.relatedTarget as Node)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="focus-ring inline-flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-left text-sm font-semibold text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-semibold text-white shadow-sm">
          {initials}
        </span>
        <span className="hidden min-w-0 flex-col sm:flex">
          <span className="truncate text-sm font-semibold text-slate-900">{displayName}</span>
          <span className="truncate text-xs text-slate-400">{email}</span>
        </span>
        <span className={clsx("text-slate-400 transition-transform", open && "rotate-180")}>▾</span>
      </button>

      <div
        role="menu"
        className={clsx(
          "absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-xl border border-slate-200 bg-white p-2 text-sm shadow-xl transition-opacity duration-200",
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        <div className="px-2 pb-2">
          <p className="text-sm font-semibold text-slate-900">Signed in as</p>
          <p className="truncate text-xs text-slate-500">{email}</p>
        </div>
        <ul className="space-y-1" role="none">
          {actions.map((action) => (
            <li key={action.id} role="none">
              <button
                type="button"
                role="menuitem"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                onClick={() => {
                  setOpen(false);
                  action.onSelect();
                }}
              >
                <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-500">
                  {action.icon ?? action.label.charAt(0).toUpperCase()}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate">{action.label}</span>
                  {action.description ? (
                    <span className="truncate text-xs font-normal text-slate-400">{action.description}</span>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-2 border-t border-slate-200 pt-2">
          <button
            type="button"
            role="menuitem"
            className="focus-ring flex w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-brand-200 hover:text-brand-700"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            disabled={signingOut}
          >
            <span>Sign out</span>
            {signingOut ? <Spinner /> : null}
          </button>
        </div>
      </div>
    </div>
  );
}

function deriveInitials(source: string) {
  const parts = source
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length === 0) {
    return "•";
  }
  if (parts.length === 1) {
    return parts[0].charAt(0).toUpperCase();
  }
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-brand-600"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
    >
      <path d="M10 3a7 7 0 1 1-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
