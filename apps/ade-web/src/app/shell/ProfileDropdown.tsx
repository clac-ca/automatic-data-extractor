import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
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
  readonly tone?: "default" | "header";
}

const MENU_ANIMATION_MS = 140;
const MENU_FALLBACK_WIDTH = 288;
const MENU_OFFSET = 8;
const MENU_VIEWPORT_PADDING = 12;

export function ProfileDropdown({ displayName, email, actions = [], tone = "default" }: ProfileDropdownProps) {
  const menuId = useId();

  const [open, setOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);

  const [isSigningOut, setIsSigningOut] = useState(false);

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();
  const initials = useMemo(() => deriveInitials(displayName || email), [displayName, email]);
  const isHeaderTone = tone === "header";

  const closeMenu = useCallback((opts?: { restoreFocus?: boolean }) => {
    setOpen(false);

    // For Esc: restore focus to trigger (Radix-like behavior).
    if (opts?.restoreFocus) {
      requestAnimationFrame(() => triggerRef.current?.focus({ preventScroll: true }));
    }
  }, []);

  const updateMenuPosition = useCallback(() => {
    if (typeof window === "undefined") return;
    if (!triggerRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const menuWidth = menuRef.current?.offsetWidth ?? MENU_FALLBACK_WIDTH;
    const menuHeight = menuRef.current?.offsetHeight ?? 0;

    const maxLeft = Math.max(MENU_VIEWPORT_PADDING, window.innerWidth - menuWidth - MENU_VIEWPORT_PADDING);
    const maxTop = Math.max(MENU_VIEWPORT_PADDING, window.innerHeight - menuHeight - MENU_VIEWPORT_PADDING);

    let left = triggerRect.right - menuWidth;
    let top = triggerRect.bottom + MENU_OFFSET;

    left = Math.min(Math.max(left, MENU_VIEWPORT_PADDING), maxLeft);
    top = Math.min(Math.max(top, MENU_VIEWPORT_PADDING), maxTop);

    setMenuPosition({ top, left });
  }, []);

  // Mount/unmount with a small transition for “polish”.
  useEffect(() => {
    if (open) {
      setIsMounted(true);
      const raf = window.requestAnimationFrame(() => {
        updateMenuPosition();
        setIsVisible(true);
      });
      return () => window.cancelAnimationFrame(raf);
    }

    // Start exit transition
    setIsVisible(false);
    setMenuPosition(null);
    const t = window.setTimeout(() => setIsMounted(false), MENU_ANIMATION_MS);
    return () => window.clearTimeout(t);
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open) return;

    const handlePositionUpdate = () => updateMenuPosition();
    window.addEventListener("resize", handlePositionUpdate);
    window.addEventListener("scroll", handlePositionUpdate, true);
    return () => {
      window.removeEventListener("resize", handlePositionUpdate);
      window.removeEventListener("scroll", handlePositionUpdate, true);
    };
  }, [open, updateMenuPosition]);

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
          "focus-ring inline-flex items-center gap-3 rounded-xl border px-2.5 py-1.5 text-left text-sm font-semibold transition",
          isHeaderTone
            ? "border-header-border/40 bg-header/25 text-header-foreground shadow-none hover:border-header-border/70 hover:bg-header/30"
            : "border-border bg-card text-muted-foreground shadow-sm hover:border-border-strong hover:text-foreground",
          open && (isHeaderTone ? "border-header-ring ring-2 ring-header-ring/30" : "border-brand-400 ring-2 ring-brand-500/10"),
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
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-semibold text-on-brand shadow-sm">
          {initials}
        </span>
        <span className="hidden min-w-0 flex-col sm:flex">
          <span className={clsx("truncate text-sm font-semibold", isHeaderTone ? "text-header-foreground" : "text-foreground")}>
            {displayName}
          </span>
          <span className={clsx("truncate text-xs", isHeaderTone ? "text-header-muted" : "text-muted-foreground")}>
            {email}
          </span>
        </span>
        <ChevronIcon
          className={clsx(
            "transition-transform duration-150",
            isHeaderTone ? "text-header-muted" : "text-muted-foreground",
            open && "rotate-180",
          )}
        />
      </button>

      {isMounted && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={menuRef}
              id={menuId}
              role="menu"
              tabIndex={-1}
              className={clsx(
                "fixed w-72 origin-top-right rounded-xl border border-border bg-popover p-2 text-sm shadow-2xl ring-1 ring-border/50",
                "isolate",
                "transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none",
                isVisible ? "opacity-100 translate-y-0 scale-100" : "pointer-events-none opacity-0 -translate-y-1 scale-[0.98]",
              )}
              style={
                menuPosition
                  ? {
                      top: menuPosition.top,
                      left: menuPosition.left,
                      position: "fixed",
                      zIndex: 90,
                      backgroundColor: "rgb(var(--sys-color-surface-elevated))",
                    }
                  : { top: 0, left: 0, visibility: "hidden" }
              }
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
                <p className="text-sm font-semibold text-foreground">Signed in as</p>
                <p className="truncate text-xs text-muted-foreground">{email}</p>
              </div>

              <ul className="space-y-1" role="none">
                {actions.map((action) => (
                  <li key={action.id} role="none">
                    <button
                      type="button"
                      role="menuitem"
                      data-menu-item
                      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
                      onClick={() => handleMenuAction(action.onSelect)}
                    >
                      <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-muted text-xs font-semibold text-muted-foreground">
                        {action.icon ?? action.label.charAt(0).toUpperCase()}
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate">{action.label}</span>
                        {action.description ? (
                          <span className="truncate text-xs font-normal text-muted-foreground">{action.description}</span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>

              <div className="mt-3 border-t border-border pt-3">
                <button
                  type="button"
                  role="menuitem"
                  data-menu-item
                  className="focus-ring flex w-full items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-muted-foreground transition hover:border-brand-400 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={handleSignOut}
                  disabled={isSigningOut}
                >
                  <span>Sign out</span>
                  {isSigningOut ? <Spinner /> : null}
                </button>
              </div>
            </div>,
            document.body,
          )
        : null}
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
