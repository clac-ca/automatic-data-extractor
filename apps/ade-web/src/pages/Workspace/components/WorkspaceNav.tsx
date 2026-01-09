import * as React from "react";
import clsx from "clsx";

import { NavLink } from "@app/navigation/Link";
import {
  getWorkspacePrimaryNavigation,
  type WorkspaceNavigationItem,
} from "@pages/Workspace/components/workspaceNavigation";
import type { WorkspaceProfile } from "@schema/workspaces";
import { GearIcon, PinIcon, UnpinIcon } from "@components/icons";

export const WORKSPACE_NAV_RAIL_WIDTH = "4.5rem";
export const WORKSPACE_NAV_DRAWER_WIDTH = "16rem";

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
  readonly className?: string;
}

export function WorkspaceNav({
  workspace,
  isPinned,
  onTogglePinned,
  items,
  className,
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

  const openTimer = React.useRef<number | null>(null);
  const closeTimer = React.useRef<number | null>(null);

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

  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();

      // Mark keyboard intent for focus-driven behavior.
      if (key === "tab" || key.startsWith("arrow")) {
        setInputMode("keyboard");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const panelExpanded = isPinned || isPeekOpen;
  const overlayActive = !isPinned && panelExpanded;

  // Key design choice:
  // - Layout width depends ONLY on pin state.
  // - Unpinned: layout stays rail width (no page shift), panel overlays when expanded.
  // - Pinned: layout becomes drawer width (pushes content).
  const layoutWidth = isPinned ? WORKSPACE_NAV_DRAWER_WIDTH : WORKSPACE_NAV_RAIL_WIDTH;
  const panelWidth = panelExpanded ? WORKSPACE_NAV_DRAWER_WIDTH : WORKSPACE_NAV_RAIL_WIDTH;
  return (
    <aside
      className={clsx(
        "relative hidden min-h-0 flex-shrink-0 bg-sidebar text-sidebar-foreground lg:flex",
        "border-r border-sidebar-border",
        "transition-[width] duration-200 ease-out motion-reduce:transition-none",
        className,
      )}
      style={{ width: layoutWidth, willChange: "width" }}
      aria-label="Primary workspace navigation"
      data-pinned={isPinned ? "true" : "false"}
      data-expanded={panelExpanded ? "true" : "false"}
    >
      {/* The panel is absolutely positioned so it can expand over the page without shifting layout when unpinned */}
      <div
        className={clsx(
          "absolute inset-y-0 left-0 z-40 flex min-h-0 flex-col bg-sidebar text-sidebar-foreground",
          "border-r border-sidebar-border",
          "transition-[width,box-shadow] duration-200 ease-out motion-reduce:transition-none",
          // When unpinned and expanded, add depth to communicate “overlay”
          overlayActive && "bg-sidebar/95 shadow-2xl ring-1 ring-sidebar-border/50 backdrop-blur-sm",
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
      <nav
        className={clsx(
          "flex-1 overflow-y-auto",
          "overflow-x-hidden",
          expanded ? "px-3 pt-3 pb-4" : "px-2 pt-3 pb-3",
        )}
        aria-label="Workspace sections"
      >
        <WorkspaceNavList items={items} variant={variant} />
      </nav>

      {/* Footer */}
      <div className={clsx("border-t border-sidebar-border", expanded ? "px-3 py-3" : "px-2 py-2")}>
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
        <p className="mb-2 px-2 text-[0.63rem] font-semibold uppercase tracking-[0.4em] text-sidebar-foreground">
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
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
                  expanded ? "px-3 py-2" : "justify-center px-2 py-2",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={clsx(
                      "flex h-10 w-10 items-center justify-center rounded-xl",
                      "transition-colors duration-150 motion-reduce:transition-none",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "bg-sidebar-accent/70 text-sidebar-foreground group-hover:bg-sidebar-accent group-hover:text-sidebar-accent-foreground",
                    )}
                  >
                    <item.icon
                      className={clsx(
                        "h-5 w-5 transition-colors duration-150",
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
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
          expanded ? "px-2 py-2" : "justify-center px-2 py-2",
          isActive
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-xl",
              "transition-colors duration-150 motion-reduce:transition-none",
              isActive
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "bg-sidebar-accent/70 text-sidebar-foreground group-hover:bg-sidebar-accent group-hover:text-sidebar-accent-foreground",
            )}
            aria-hidden
          >
            <GearIcon className="h-5 w-5" />
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

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-pressed={isPinned}
      title={label}
      className={clsx(
        "group relative flex w-full items-center rounded-lg",
        "transition-colors duration-150 motion-reduce:transition-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
        expanded ? "px-2 py-2" : "justify-center px-2 py-2",
        "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
      )}
    >
      <span
        className={clsx(
          "flex h-10 w-10 items-center justify-center rounded-xl bg-sidebar-accent/70 text-sidebar-foreground transition-colors duration-150 group-hover:bg-sidebar-accent group-hover:text-sidebar-accent-foreground",
        )}
        aria-hidden
      >
        {isPinned ? <UnpinIcon className="h-4 w-4" /> : <PinIcon className="h-4 w-4" />}
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
      </span>

    </button>
  );
}

function isPlainLeftClick(e: React.MouseEvent) {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey;
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
