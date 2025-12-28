import clsx from "clsx";

import { NavLink } from "@app/nav/Link";
import { getWorkspacePrimaryNavigation, type WorkspaceNavigationItem } from "@screens/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@shared/workspaces";

const NAV_RAIL_WIDTH = "4.5rem";
const NAV_DRAWER_WIDTH = "16rem";

export interface WorkspaceNavProps {
  readonly workspace: WorkspaceProfile;
  readonly isPinned: boolean;
  readonly onTogglePinned: () => void;
  readonly items?: readonly WorkspaceNavigationItem[];
  readonly onGoToWorkspaces: () => void;
}

export function WorkspaceNav({ workspace, isPinned, onTogglePinned, items, onGoToWorkspaces }: WorkspaceNavProps) {
  const navItems = items ?? getWorkspacePrimaryNavigation(workspace);
  const workspaceInitials = getWorkspaceInitials(workspace.name);
  const variant: NavVariant = isPinned ? "drawer" : "rail";
  const isExpanded = variant === "drawer";
  const navWidth = isExpanded ? NAV_DRAWER_WIDTH : NAV_RAIL_WIDTH;
  const switcherLabel = `Switch workspace: ${workspace.name}`;

  return (
    <aside
      className="relative hidden h-screen flex-shrink-0 border-r border-slate-200 bg-white transition-[width] duration-200 ease-out lg:flex"
      style={{ width: navWidth }}
      aria-label="Primary workspace navigation"
    >
      <div className="flex h-full w-full flex-col">
        <div className={clsx("border-b border-slate-200", isExpanded ? "px-3 py-3" : "px-2 py-2")}>
          <button
            type="button"
            onClick={onGoToWorkspaces}
            aria-label={switcherLabel}
            title={workspace.name}
            className={clsx(
              "group flex w-full rounded-xl transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
              isExpanded ? "items-center gap-3 px-2 py-2 hover:bg-slate-50" : "flex-col items-center gap-1 px-1 py-2 hover:bg-slate-50",
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
              <span className="text-[0.58rem] font-semibold uppercase tracking-[0.28em] text-slate-400">
                Workspace
              </span>
            )}
            {isExpanded ? (
              <span className="text-slate-400 transition group-hover:text-slate-600" aria-hidden>
                <ChevronDownIcon />
              </span>
            ) : null}
          </button>
        </div>

        <nav
          className={clsx("flex-1 overflow-y-auto", isExpanded ? "px-3 py-4" : "px-2 py-3")}
          aria-label="Workspace sections"
        >
          <WorkspaceNavList items={navItems} variant={variant} />
        </nav>

        <div className={clsx("border-t border-slate-200", isExpanded ? "px-3 py-3" : "px-2 py-2")}>
          <NavToggleButton isExpanded={isExpanded} onToggle={onTogglePinned} />
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
              title={!isExpanded ? item.label : undefined}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  "group w-full rounded-lg transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isExpanded
                    ? "flex items-center gap-3 px-3 py-2 text-sm font-semibold"
                    : "flex flex-col items-center gap-1.5 px-2 py-2 text-[0.65rem] font-medium",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={clsx(
                      "flex h-9 w-9 items-center justify-center rounded-lg transition",
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
                      "block w-full min-w-0 truncate text-center leading-tight",
                      isExpanded && "text-left",
                    )}
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

type NavVariant = "rail" | "drawer";

function NavToggleButton({ isExpanded, onToggle }: { readonly isExpanded: boolean; readonly onToggle: () => void }) {
  const label = isExpanded ? "Collapse navigation" : "Expand navigation";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-expanded={isExpanded}
      title={label}
      className={clsx(
        "group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-xs font-semibold text-slate-500 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
        isExpanded ? "justify-start" : "flex-col gap-1 text-[0.65rem]",
        "hover:bg-slate-100 hover:text-slate-700",
      )}
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition group-hover:bg-slate-200">
        {isExpanded ? <CollapseIcon /> : <ExpandIcon />}
      </span>
      <span className={clsx("block min-w-0 truncate", !isExpanded && "text-center")}>
        {isExpanded ? "Collapse" : "Expand"}
      </span>
    </button>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="m6 8 4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CollapseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="M12.5 6 9 10l3.5 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ExpandIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="m7.5 6 3.5 4-3.5 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) {
    return "WS";
  }
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}
