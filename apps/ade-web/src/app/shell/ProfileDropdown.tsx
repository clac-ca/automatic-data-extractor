import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import clsx from "clsx";

import { useNavigate } from "@app/nav/history";

interface ProfileDropdownAction {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly onSelect: () => void;
}

interface ProfileDropdownProps {
  readonly displayName: string;
  readonly email: string;
  readonly actions?: readonly ProfileDropdownAction[];
}

const MENU_ANIMATION_MS = 140;

export function ProfileDropdown({ displayName, email, actions = [] }: ProfileDropdownProps) {
  const menuId = useId();

  const [open, setOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  const [isSigningOut, setIsSigningOut] = useState(false);

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();

  const initials = useMemo(() => deriveInitials(displayName || email), [displayName, email]);

  const closeMenu = useCallback((opts?: { restoreFocus?: boolean }) => {
    setOpen(false);

    // For Esc: restore focus to trigger (Radix-like behavior).
    if (opts?.restoreFocus) {
      requestAnimationFrame(() => triggerRef.current?.focus({ preventScroll: true }));
    }
  }, []);

  // Mount/unmount with a small transition for “polish”.
  useEffect(() => {
    if (open) {
      setIsMounted(true);
      requestAnimationFrame(() => setIsVisible(true));
      return;
    }

    // Start exit transition
    setIsVisible(false);
    const t = window.setTimeout(() => setIsMounted(false), MENU_ANIMATION_MS);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;

      if (menuRef.current?.contains(target) || triggerRef.current?.contains(target)) return;

      // Click outside: close without stealing focus.
      closeMenu();
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeMenu({ restoreFocus: true });
      }
    };

    window.addEventListener("pointerdown", handlePointerDown, { passive: true });
    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [closeMenu, open]);

  useEffect(() => {
    if (!open) return;

    requestAnimationFrame(() => {
      const firstMenuItem = menuRef.current?.querySelector<HTMLButtonElement>("button[data-menu-item]");
      firstMenuItem?.focus({ preventScroll: true });
    });
  }, [open]);

  const handleMenuAction = useCallback(
    (action: () => void) => {
      closeMenu();
      action();
    },
    [closeMenu],
  );

  const handleSignOut = useCallback(async () => {
    if (isSigningOut) return;

    closeMenu();
    setIsSigningOut(true);
    navigate("/logout", { replace: true });
  }, [closeMenu, isSigningOut, navigate]);

  const focusMenuItem = (index: number) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("button[data-menu-item]") ?? []);
    if (items.length === 0) return;
    const clamped = ((index % items.length) + items.length) % items.length;
    items[clamped]?.focus({ preventScroll: true });
  };

  const moveFocus = (delta: number) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("button[data-menu-item]") ?? []);
    if (items.length === 0) return;

    const active = document.activeElement as HTMLButtonElement | null;
    const currentIndex = active ? items.indexOf(active) : -1;
    const nextIndex = currentIndex === -1 ? 0 : currentIndex + delta;
    focusMenuItem(nextIndex);
  };

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        className={clsx(
          "focus-ring inline-flex items-center gap-3 rounded-xl border bg-white px-2.5 py-1.5 text-left text-sm font-semibold text-slate-700 shadow-sm transition",
          "hover:border-slate-300 hover:text-slate-900",
          open ? "border-brand-200 ring-2 ring-brand-500/10" : "border-slate-200",
        )}
        aria-haspopup="menu"
        aria-controls={menuId}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(e) => {
          // Open with Enter/Space/ArrowDown like native menus.
          if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-semibold text-white shadow-sm">
          {initials}
        </span>
        <span className="hidden min-w-0 flex-col sm:flex">
          <span className="truncate text-sm font-semibold text-slate-900">{displayName}</span>
          <span className="truncate text-xs text-slate-400">{email}</span>
        </span>
        <ChevronIcon className={clsx("text-slate-400 transition-transform duration-150", open && "rotate-180")} />
      </button>

      {isMounted ? (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          className={clsx(
            "absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-xl border border-slate-200 bg-white p-2 text-sm shadow-xl",
            "transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none",
            isVisible ? "opacity-100 translate-y-0 scale-100" : "pointer-events-none opacity-0 -translate-y-1 scale-[0.98]",
          )}
          onKeyDown={(e) => {
            // Arrow key navigation (Radix-like).
            if (e.key === "ArrowDown") {
              e.preventDefault();
              moveFocus(1);
              return;
            }
            if (e.key === "ArrowUp") {
              e.preventDefault();
              moveFocus(-1);
              return;
            }
            if (e.key === "Home") {
              e.preventDefault();
              focusMenuItem(0);
              return;
            }
            if (e.key === "End") {
              e.preventDefault();
              focusMenuItem(Number.MAX_SAFE_INTEGER);
              return;
            }
            if (e.key === "Escape") {
              e.preventDefault();
              closeMenu({ restoreFocus: true });
            }
          }}
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
                  data-menu-item
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                  onClick={() => handleMenuAction(action.onSelect)}
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
              data-menu-item
              className="focus-ring flex w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-brand-200 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={handleSignOut}
              disabled={isSigningOut}
            >
              <span>Sign out</span>
              {isSigningOut ? <Spinner /> : null}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function deriveInitials(source: string) {
  const parts = source
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) return "•";
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin text-brand-600" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M10 3a7 7 0 1 1-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={clsx("h-4 w-4", className)} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
