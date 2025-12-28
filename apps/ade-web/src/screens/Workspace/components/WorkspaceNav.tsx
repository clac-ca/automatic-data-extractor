import * as React from "react";
import clsx from "clsx";

import { NavLink } from "@app/nav/Link";
import {
  getWorkspacePrimaryNavigation,
  type WorkspaceNavigationItem,
} from "@screens/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@shared/workspaces";

/**
 * Inspired by "mini variant drawer" / "icon-collapsed sidebar" patterns:
 * - icons-only rail (minimal space)
 * - expands on hover or keyboard focus when unpinned
 * - can be pinned open for persistent drawer behavior
 *
 * References:
 * - MUI Drawer mini variant
 * - shadcn/ui Sidebar (collapsible icon mode, sticky header/footer)
 */

const NAV_RAIL_WIDTH = "4.5rem";
const NAV_DRAWER_WIDTH = "16rem";

// Small delays make hover-expansion feel intentional (less jitter when cursor passes by).
const HOVER_OPEN_DELAY_MS = 60;
const HOVER_CLOSE_DELAY_MS = 120;

export interface WorkspaceNavProps {
  readonly workspace: WorkspaceProfile;
  readonly isPinned: boolean;
  readonly onTogglePinned: () => void;
  readonly items?: readonly WorkspaceNavigationItem[];
  readonly onGoToWorkspaces: () => void;
}

export function WorkspaceNav({
  workspace,
  isPinned,
  onTogglePinned,
  items,
  onGoToWorkspaces,
}: WorkspaceNavProps) {
  const navItems = items ?? getWorkspacePrimaryNavigation(workspace);
  const workspaceInitials = getWorkspaceInitials(workspace.name);

  // When unpinned, we temporarily expand on hover/focus for a "peek" drawer.
  const [isPreviewOpen, setIsPreviewOpen] = React.useState(false);

  const openTimer = React.useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const closeTimer = React.useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const rootRef = React.useRef<HTMLDivElement | null>(null);

  const isExpanded = isPinned || isPreviewOpen;
  const variant: NavVariant = isExpanded ? "drawer" : "rail";
  const navWidth = isExpanded ? NAV_DRAWER_WIDTH : NAV_RAIL_WIDTH;

  const switcherLabel = `Switch workspace: ${workspace.name}`;

  const clearTimers = React.useCallback(() => {
    if (openTimer.current) {
      window.clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    if (closeTimer.current) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);

  const scheduleOpen = React.useCallback(() => {
    if (isPinned) return;
    clearTimers();
    openTimer.current = window.setTimeout(() => setIsPreviewOpen(true), HOVER_OPEN_DELAY_MS);
  }, [clearTimers, isPinned]);

  const scheduleClose = React.useCallback(() => {
    if (isPinned) return;
    clearTimers();
    closeTimer.current = window.setTimeout(() => setIsPreviewOpen(false), HOVER_CLOSE_DELAY_MS);
  }, [clearTimers, isPinned]);

  const openImmediately = React.useCallback(() => {
    if (isPinned) return;
    clearTimers();
    setIsPreviewOpen(true);
  }, [clearTimers, isPinned]);

  const closeImmediately = React.useCallback(() => {
    if (isPinned) return;
    clearTimers();
    setIsPreviewOpen(false);
  }, [clearTimers, isPinned]);

  // If the user pins the sidebar, we no longer need preview state.
  React.useEffect(() => {
    if (isPinned) {
      clearTimers();
      setIsPreviewOpen(false);
    }
  }, [clearTimers, isPinned]);

  // Clean up timers on unmount.
  React.useEffect(() => clearTimers, [clearTimers]);

  // Keyboard affordances:
  // - Esc closes preview (when unpinned)
  // - Ctrl/Cmd + B toggles pin (common sidebar shortcut)
  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!rootRef.current) return;

      // Close preview with Escape.
      if (e.key === "Escape" && isPreviewOpen && !isPinned) {
        e.preventDefault();
        closeImmediately();
        return;
      }

      // Toggle pin with Ctrl/Cmd + B (ignore while typing).
      const key = e.key.toLowerCase();
      if ((e.metaKey || e.ctrlKey) && key === "b") {
        const target = e.target as EventTarget | null;
        if (isEditableTarget(target)) return;

        e.preventDefault();
        onTogglePinned();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeImmediately, isPinned, isPreviewOpen, onTogglePinned]);

  const handleNavigate = React.useCallback(() => {
    // Mimic “temporary drawer closes on selection” behavior for the hover-preview state.
    if (!isPinned) setIsPreviewOpen(false);
  }, [isPinned]);

  return (
    <aside
      className={clsx(
        "relative hidden h-screen flex-shrink-0 lg:flex",
        "transition-[width] duration-200 ease-out motion-reduce:transition-none",
        // Subtle shadow when it's a temporary preview (feels like a “peek” panel).
        !isPinned && isExpanded && "shadow-lg",
        "bg-white",
        "border-r border-slate-200",
      )}
      style={{ width: navWidth }}
      aria-label="Primary workspace navigation"
    >
      <div
        ref={rootRef}
        className="flex h-full w-full flex-col"
        onMouseEnter={scheduleOpen}
        onMouseLeave={scheduleClose}
        onFocusCapture={openImmediately}
        onBlurCapture={() => {
          if (isPinned) return;

          // Let focus settle, then check if focus left the nav entirely.
          requestAnimationFrame(() => {
            const root = rootRef.current;
            if (!root) return;
            const active = document.activeElement;
            if (active && root.contains(active)) return;
            scheduleClose();
          });
        }}
      >
        {/* Header / Workspace Switcher */}
        <div className={clsx("border-b border-slate-200", isExpanded ? "px-3 py-3" : "px-2 py-2")}>
          <button
            type="button"
            onClick={onGoToWorkspaces}
            aria-label={switcherLabel}
            title={!isExpanded ? switcherLabel : workspace.name}
            className={clsx(
              "group relative flex w-full rounded-xl transition",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
              isExpanded ? "items-center gap-3 px-2 py-2 hover:bg-slate-50" : "items-center justify-center px-2 py-2 hover:bg-slate-50",
            )}
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-xs font-semibold uppercase text-white shadow-sm transition group-hover:bg-brand-600">
              {workspaceInitials}
            </span>

            {isExpanded ? (
              <div className="min-w-0 flex-1 text-left">
                <p className="truncate text-sm font-semibold text-slate-900">{workspace.name}</p>
                <p className="text-xs text-slate-500">Switch workspace</p>
              </div>
            ) : (
              <>
                <span className="sr-only">{switcherLabel}</span>
                <RailTooltip label={workspace.name} />
              </>
            )}

            {isExpanded ? (
              <span className="text-slate-400 transition group-hover:text-slate-600" aria-hidden>
                <ChevronDownIcon />
              </span>
            ) : null}
          </button>
        </div>

        {/* Primary Nav */}
        <nav
          className={clsx(
            "flex-1 overflow-y-auto",
            // Allow tooltips to escape in rail mode without horizontal scrollbars.
            "overflow-x-visible",
            isExpanded ? "px-3 py-4" : "px-2 py-3",
          )}
          aria-label="Workspace sections"
        >
          <WorkspaceNavList items={navItems} variant={variant} onNavigate={handleNavigate} />
        </nav>

        {/* Footer / Pin Toggle */}
        <div className={clsx("border-t border-slate-200", isExpanded ? "px-3 py-3" : "px-2 py-2")}>
          <NavPinButton isPinned={isPinned} isExpanded={isExpanded} onToggle={onTogglePinned} />
        </div>
      </div>
    </aside>
  );
}

interface WorkspaceNavListProps {
  readonly items: readonly WorkspaceNavigationItem[];
  readonly variant?: NavVariant;
  readonly onNavigate?: () => void;
  readonly className?: string;
  readonly showHeading?: boolean;
}

/**
 * Drawer variant: icon + label rows
 * Rail variant: icon-only buttons + tooltip (minimal space)
 */
export function WorkspaceNavList({
  items,
  variant = "drawer",
  onNavigate,
  className,
  showHeading = true,
}: WorkspaceNavListProps) {
  const isExpanded = variant === "drawer";

  return (
    <>
      {showHeading && isExpanded ? (
        <p className="mb-3 px-2 text-[0.63rem] font-semibold uppercase tracking-[0.4em] text-slate-400/90">
          Workspace
        </p>
      ) : null}

      <ul className={clsx("flex flex-col", isExpanded ? "gap-1.5" : "gap-2", className)}>
        {items.map((item) => (
          <li key={item.id} className="w-full">
            <NavLink
              to={item.href}
              end={!(item.matchPrefix ?? false)}
              onClick={onNavigate}
              title={!isExpanded ? item.label : undefined}
              aria-label={!isExpanded ? item.label : undefined}
              className={({ isActive }) =>
                clsx(
                  "group relative w-full rounded-lg transition",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isExpanded ? "flex items-center gap-3 px-3 py-2 text-sm font-semibold" : "flex items-center justify-center px-2 py-2",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={clsx(
                      "flex items-center justify-center rounded-lg transition",
                      isExpanded ? "h-9 w-9" : "h-10 w-10 rounded-xl",
                      isActive ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-500 group-hover:bg-slate-200",
                    )}
                  >
                    <item.icon
                      className={clsx(
                        "h-5 w-5 transition-colors duration-150",
                        isActive ? "text-brand-600" : "text-slate-500",
                      )}
                      aria-hidden
                    />
                  </span>

                  {isExpanded ? (
                    <span className="block min-w-0 flex-1 truncate text-left leading-tight">{item.label}</span>
                  ) : (
                    <>
                      <span className="sr-only">{item.label}</span>
                      <RailTooltip label={item.label} />
                    </>
                  )}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </>
  );
}

type NavVariant = "rail" | "drawer";

function NavPinButton({
  isPinned,
  isExpanded,
  onToggle,
}: {
  readonly isPinned: boolean;
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
}) {
  const label = isPinned ? "Unpin sidebar" : "Pin sidebar";
  const shortcutHint = "Ctrl/⌘B";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-pressed={isPinned}
      title={!isExpanded ? `${label} (${shortcutHint})` : undefined}
      className={clsx(
        "group relative flex w-full items-center rounded-lg transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
        isExpanded ? "gap-3 px-2 py-2 text-xs font-semibold text-slate-600" : "justify-center px-2 py-2",
        "hover:bg-slate-100 hover:text-slate-800",
      )}
    >
      <span
        className={clsx(
          "flex items-center justify-center transition",
          isExpanded ? "h-9 w-9 rounded-lg bg-slate-100 text-slate-600 group-hover:bg-slate-200" : "h-10 w-10 rounded-xl bg-slate-100 text-slate-600 group-hover:bg-slate-200",
        )}
        aria-hidden
      >
        {isPinned ? <UnpinIcon /> : <PinIcon />}
      </span>

      {isExpanded ? (
        <span className="block min-w-0 truncate">
          {isPinned ? "Pinned" : "Pin sidebar"}
          <span className="ml-2 text-[0.7rem] font-semibold text-slate-400">{shortcutHint}</span>
        </span>
      ) : (
        <>
          <span className="sr-only">{label}</span>
          <RailTooltip label={isPinned ? "Unpin sidebar" : "Pin sidebar"} />
        </>
      )}
    </button>
  );
}

/**
 * Tooltip used in rail mode (icon-only).
 * Uses only Tailwind utilities (no dependency), and triggers on hover and focus-visible.
 */
function RailTooltip({ label }: { readonly label: string }) {
  return (
    <span
      className={clsx(
        "pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap",
        "rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg",
        "opacity-0 transition-opacity duration-150",
        "group-hover:opacity-100 group-focus-visible:opacity-100",
      )}
      aria-hidden
    >
      {label}
    </span>
  );
}

function isEditableTarget(target: EventTarget | null) {
  if (!target) return false;
  if (!(target instanceof HTMLElement)) return false;

  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (target.isContentEditable) return true;

  // Also ignore common “editor” containers
  if (target.closest?.("[contenteditable='true']")) return true;

  return false;
}

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="m6 8 4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path
        d="M7 3h6l-1 6 3 3H5l3-3-1-6Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 12v5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UnpinIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path
        d="M7 3h6l-1 6 3 3H5l3-3-1-6Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M6 16 14 8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "WS";
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}
