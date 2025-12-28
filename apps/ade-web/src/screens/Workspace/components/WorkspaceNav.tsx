import * as React from "react";
import clsx from "clsx";

import { NavLink } from "@app/nav/Link";
import {
  getWorkspacePrimaryNavigation,
  type WorkspaceNavigationItem,
} from "@screens/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@shared/workspaces";

const NAV_RAIL_WIDTH = "4.5rem";
const NAV_DRAWER_WIDTH = "16rem";

// Hover timings tuned to feel intentional (avoid flicker when moving across the rail)
const HOVER_OPEN_DELAY_MS = 70;
const HOVER_CLOSE_DELAY_MS = 140;

type NavVariant = "rail" | "drawer";
type InputMode = "pointer" | "keyboard";

export interface WorkspaceNavProps {
  readonly workspace: WorkspaceProfile;
  readonly isPinned: boolean;
  readonly onTogglePinned: () => void;
  readonly items?: readonly WorkspaceNavigationItem[];
}

export function WorkspaceNav({
  workspace,
  isPinned,
  onTogglePinned,
  items,
}: WorkspaceNavProps) {
  const allItems = items ?? getWorkspacePrimaryNavigation(workspace);

  // Move Workspace Settings into the footer (gear) if we can identify it.
  const settingsItem = pickWorkspaceSettingsItem(allItems);
  const navItems = settingsItem ? allItems.filter((i) => i.id !== settingsItem.id) : allItems;

  // Interaction state:
  // - unpinned: expands on hover (overlay) and collapses on mouse leave
  // - keyboard users: focus can keep it open (common accessibility expectation)
  const [inputMode, setInputMode] = React.useState<InputMode>("pointer");
  const [isHovering, setIsHovering] = React.useState(false);
  const [isFocusWithin, setIsFocusWithin] = React.useState(false);
  const [isPeekOpen, setIsPeekOpen] = React.useState(false);

  const openTimer = React.useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const closeTimer = React.useRef<ReturnType<typeof window.setTimeout> | null>(null);

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

  // Only let focus keep it open for keyboard navigation.
  // This prevents the “I clicked a link and it stayed open until I clicked the page” effect.
  const wantsOpen = !isPinned && (isHovering || (isFocusWithin && inputMode === "keyboard"));

  React.useEffect(() => {
    if (isPinned) {
      clearTimers();
      setIsPeekOpen(false);
      return;
    }

    // If already in the desired state, do nothing.
    if (wantsOpen && isPeekOpen) return;
    if (!wantsOpen && !isPeekOpen) return;

    clearTimers();

    if (wantsOpen) {
      // Keyboard focus should feel immediate; hover gets a tiny delay.
      if (isFocusWithin && inputMode === "keyboard") {
        setIsPeekOpen(true);
        return;
      }
      openTimer.current = window.setTimeout(() => setIsPeekOpen(true), HOVER_OPEN_DELAY_MS);
    } else {
      closeTimer.current = window.setTimeout(() => setIsPeekOpen(false), HOVER_CLOSE_DELAY_MS);
    }
  }, [clearTimers, inputMode, isFocusWithin, isHovering, isPeekOpen, isPinned, wantsOpen]);

  React.useEffect(() => clearTimers, [clearTimers]);

  // Global shortcut: Ctrl/⌘B toggles pin (common in app shells, e.g. IDEs).
  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();

      // Mark keyboard intent for focus-driven behavior.
      if (key === "tab" || key.startsWith("arrow")) {
        setInputMode("keyboard");
      }

      if ((e.metaKey || e.ctrlKey) && key === "b") {
        const target = e.target as EventTarget | null;
        if (isEditableTarget(target)) return;
        e.preventDefault();
        onTogglePinned();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onTogglePinned]);

  const panelExpanded = isPinned || isPeekOpen;

  // Key design choice:
  // - Layout width depends ONLY on pin state.
  // - Unpinned: layout stays rail width (no page shift), panel overlays when expanded.
  // - Pinned: layout becomes drawer width (pushes content).
  const layoutWidth = isPinned ? NAV_DRAWER_WIDTH : NAV_RAIL_WIDTH;
  const panelWidth = panelExpanded ? NAV_DRAWER_WIDTH : NAV_RAIL_WIDTH;
  const navHeight = "calc(100vh - var(--workspace-topbar-height, 0px))";

  return (
    <aside
      className={clsx(
        "relative hidden min-h-0 flex-shrink-0 bg-white lg:flex",
        "border-r border-slate-200",
        "transition-[width] duration-200 ease-out motion-reduce:transition-none",
      )}
      style={{ width: layoutWidth, height: navHeight, willChange: "width" }}
      aria-label="Primary workspace navigation"
      data-pinned={isPinned ? "true" : "false"}
      data-expanded={panelExpanded ? "true" : "false"}
    >
      {/* The panel is absolutely positioned so it can expand over the page without shifting layout when unpinned */}
      <div
        className={clsx(
          "absolute inset-y-0 left-0 z-40 flex min-h-0 flex-col bg-white",
          "border-r border-slate-300/80",
          "transition-[width,box-shadow] duration-200 ease-out motion-reduce:transition-none",
          // When unpinned and expanded, add depth to communicate “overlay”
          !isPinned && panelExpanded && "shadow-xl",
        )}
        style={{ width: panelWidth, willChange: "width" }}
        onMouseEnter={() => {
          if (!isPinned) setIsHovering(true);
        }}
        onMouseLeave={() => {
          if (!isPinned) setIsHovering(false);
        }}
        onPointerDownCapture={() => setInputMode("pointer")}
        onKeyDownCapture={(e) => {
          const key = e.key.toLowerCase();
          if (key === "tab" || key.startsWith("arrow")) setInputMode("keyboard");
        }}
        onFocusCapture={() => setIsFocusWithin(true)}
        onBlurCapture={() => {
          // Let focus settle, then see if it left the panel.
          requestAnimationFrame(() => {
            const active = document.activeElement;
            const panel = document.querySelector("[data-workspace-nav-panel='true']");
            if (panel && active && panel.contains(active)) return;
            setIsFocusWithin(false);
          });
        }}
        data-workspace-nav-panel="true"
      >
        <WorkspaceNavPanel
          items={navItems}
          settingsItem={settingsItem}
          expanded={panelExpanded}
          isPinned={isPinned}
          onTogglePinned={onTogglePinned}
        />
      </div>
    </aside>
  );
}

function WorkspaceNavPanel({
  items,
  settingsItem,
  expanded,
  isPinned,
  onTogglePinned,
}: {
  readonly items: readonly WorkspaceNavigationItem[];
  readonly settingsItem?: WorkspaceNavigationItem;
  readonly expanded: boolean;
  readonly isPinned: boolean;
  readonly onTogglePinned: () => void;
}) {
  const variant: NavVariant = expanded ? "drawer" : "rail";

  return (
    <>
      {/* Nav */}
      <nav className={clsx("flex-1 overflow-y-auto", "overflow-x-visible", expanded ? "px-3 py-4" : "px-2 py-3")} aria-label="Workspace sections">
        <WorkspaceNavList items={items} variant={variant} />
      </nav>

      {/* Footer */}
      <div className={clsx("border-t border-slate-200", expanded ? "px-3 py-3" : "px-2 py-2")}>
        <div className={clsx("flex flex-col", expanded ? "gap-1.5" : "gap-2")}>
          {settingsItem ? <WorkspaceSettingsLink item={settingsItem} expanded={expanded} /> : null}
          <NavPinButton isPinned={isPinned} expanded={expanded} onToggle={onTogglePinned} />
        </div>
      </div>
    </>
  );
}

interface WorkspaceNavListProps {
  readonly items: readonly WorkspaceNavigationItem[];
  readonly variant?: NavVariant;
  readonly onNavigate?: () => void;
  readonly className?: string;
  readonly showHeading?: boolean;
}

export function WorkspaceNavList({
  items,
  variant = "drawer",
  onNavigate,
  className,
  showHeading = true,
}: WorkspaceNavListProps) {
  const expanded = variant === "drawer";

  return (
    <>
      {showHeading && expanded ? (
        <p className="mb-3 px-2 text-[0.63rem] font-semibold uppercase tracking-[0.4em] text-slate-400/90">
          Workspace
        </p>
      ) : null}

      <ul className={clsx("flex flex-col", expanded ? "gap-1.5" : "gap-2", className)}>
        {items.map((item) => (
          <li key={item.id} className="w-full">
            <NavLink
              to={item.href}
              end={!(item.matchPrefix ?? false)}
              title={!expanded ? item.label : undefined}
              aria-label={!expanded ? item.label : undefined}
              onClick={(e) => {
                // Prevent “glitchy” feeling when clicking the already-active page.
                // (Avoid re-navigation / scroll resets / re-renders where possible.)
                if (isPlainLeftClick(e) && (e.currentTarget as HTMLElement).getAttribute("aria-current") === "page") {
                  e.preventDefault();
                  return;
                }
                onNavigate?.();
              }}
              className={({ isActive }) =>
                clsx(
                  "group relative flex w-full items-center rounded-lg",
                  "transition-colors duration-150 motion-reduce:transition-none",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  expanded ? "px-3 py-2" : "justify-center px-2 py-2",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={clsx(
                      "flex h-10 w-10 items-center justify-center rounded-xl",
                      "transition-colors duration-150 motion-reduce:transition-none",
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

                  <span
                    className={clsx(
                      "min-w-0 overflow-hidden truncate",
                      "transition-[max-width,opacity,transform,margin-left] duration-200 motion-reduce:transition-none",
                      expanded ? "ml-3 max-w-[14rem] opacity-100 translate-x-0" : "ml-0 max-w-0 opacity-0 translate-x-1",
                      "text-sm font-semibold",
                    )}
                    aria-hidden={!expanded}
                  >
                    {item.label}
                  </span>

                  {!expanded ? <RailTooltip label={item.label} /> : null}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </>
  );
}

function WorkspaceSettingsLink({ item, expanded }: { readonly item: WorkspaceNavigationItem; readonly expanded: boolean }) {
  const tooltipLabel = item.label || "Workspace settings";

  return (
    <NavLink
      to={item.href}
      end={!(item.matchPrefix ?? false)}
      title={!expanded ? tooltipLabel : undefined}
      onClick={(e) => {
        if (isPlainLeftClick(e) && (e.currentTarget as HTMLElement).getAttribute("aria-current") === "page") {
          e.preventDefault();
        }
      }}
      className={({ isActive }) =>
        clsx(
          "group relative flex w-full items-center rounded-lg",
          "transition-colors duration-150 motion-reduce:transition-none",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
          expanded ? "px-2 py-2" : "justify-center px-2 py-2",
          isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-800",
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-xl",
              "transition-colors duration-150 motion-reduce:transition-none",
              isActive ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-600 group-hover:bg-slate-200",
            )}
            aria-hidden
          >
            <GearIcon />
          </span>

          <span
            className={clsx(
              "min-w-0 overflow-hidden truncate",
              "transition-[max-width,opacity,transform,margin-left] duration-200 motion-reduce:transition-none",
              expanded ? "ml-3 max-w-[14rem] opacity-100 translate-x-0" : "ml-0 max-w-0 opacity-0 translate-x-1",
              "text-xs font-semibold",
            )}
            aria-hidden={!expanded}
          >
            Settings
          </span>

          {!expanded ? <RailTooltip label={tooltipLabel} /> : null}
        </>
      )}
    </NavLink>
  );
}

function NavPinButton({
  isPinned,
  expanded,
  onToggle,
}: {
  readonly isPinned: boolean;
  readonly expanded: boolean;
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
      title={!expanded ? `${label} (${shortcutHint})` : `${label} (${shortcutHint})`}
      className={clsx(
        "group relative flex w-full items-center rounded-lg",
        "transition-colors duration-150 motion-reduce:transition-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
        expanded ? "px-2 py-2" : "justify-center px-2 py-2",
        "text-slate-600 hover:bg-slate-100 hover:text-slate-800",
      )}
    >
      <span
        className={clsx(
          "flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600 transition-colors duration-150 group-hover:bg-slate-200",
        )}
        aria-hidden
      >
        {isPinned ? <UnpinIcon /> : <PinIcon />}
      </span>

      <span
        className={clsx(
          "min-w-0 overflow-hidden truncate",
          "transition-[max-width,opacity,transform,margin-left] duration-200 motion-reduce:transition-none",
          expanded ? "ml-3 max-w-[14rem] opacity-100 translate-x-0" : "ml-0 max-w-0 opacity-0 translate-x-1",
          "text-xs font-semibold",
        )}
        aria-hidden={!expanded}
      >
        {isPinned ? "Pinned" : "Pin sidebar"}
        <span className="ml-2 text-[0.7rem] font-semibold text-slate-400">{shortcutHint}</span>
      </span>

      {!expanded ? <RailTooltip label={label} /> : null}
    </button>
  );
}

/**
 * Tooltip used in rail mode (icon-only).
 * Keep pointer-events disabled so it never interferes with hover/leave logic.
 */
function RailTooltip({ label }: { readonly label: string }) {
  return (
    <span
      className={clsx(
        "pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap",
        "rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg",
        "opacity-0 transition-opacity duration-150 motion-reduce:transition-none",
        "group-hover:opacity-100 group-focus-visible:opacity-100",
      )}
      aria-hidden
    >
      {label}
    </span>
  );
}

function isPlainLeftClick(e: React.MouseEvent) {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey;
}

function isEditableTarget(target: EventTarget | null) {
  if (!target) return false;
  if (!(target instanceof HTMLElement)) return false;

  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (target.isContentEditable) return true;
  if (target.closest?.("[contenteditable='true']")) return true;

  return false;
}

function pickWorkspaceSettingsItem(items: readonly WorkspaceNavigationItem[]) {
  const exactIds = new Set(["settings", "workspace-settings", "workspacesettings", "preferences"]);

  const byExactId = items.find((item) => exactIds.has(item.id.toLowerCase()));
  if (byExactId) return byExactId;

  const byIdIncludes = items.find((item) => item.id.toLowerCase().includes("settings"));
  if (byIdIncludes) return byIdIncludes;

  const byHref = items.find((item) => /settings|preferences/i.test(item.href));
  if (byHref) return byHref;

  const byLabel = items.find((item) => /settings|preferences/i.test(item.label));
  return byLabel;
}

function GearIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path
        d="M10 12.6a2.6 2.6 0 1 0 0-5.2 2.6 2.6 0 0 0 0 5.2Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M16.6 10.3a7 7 0 0 0 0-.6l1.4-1.1a.8.8 0 0 0 .2-1l-1.3-2.2a.8.8 0 0 0-1-.3l-1.6.6c-.2-.2-.6-.4-.9-.5l-.2-1.7a.8.8 0 0 0-.8-.7H8.7a.8.8 0 0 0-.8.7l-.2 1.7c-.3.1-.6.3-.9.5l-1.6-.6a.8.8 0 0 0-1 .3L2.9 7.6a.8.8 0 0 0 .2 1L4.5 9.7a7 7 0 0 0 0 .6l-1.4 1.1a.8.8 0 0 0-.2 1l1.3 2.2a.8.8 0 0 0 1 .3l1.6-.6c.3.2.6.4.9.5l.2 1.7a.8.8 0 0 0 .8.7h2.6a.8.8 0 0 0 .8-.7l.2-1.7c.3-.1.6-.3.9-.5l1.6.6a.8.8 0 0 0 1-.3l1.3-2.2a.8.8 0 0 0-.2-1l-1.4-1.1Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="M7 3h6l-1 6 3 3H5l3-3-1-6Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10 12v5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UnpinIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="M7 3h6l-1 6 3 3H5l3-3-1-6Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 16 14 8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
