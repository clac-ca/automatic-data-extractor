import { NavLink } from "@app/nav/Link";
import clsx from "clsx";

import { getWorkspacePrimaryNavigation, type WorkspaceNavigationItem } from "@screens/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";

const COLLAPSED_NAV_WIDTH = "4.25rem";
const EXPANDED_NAV_WIDTH = "clamp(14rem, 20vw, 18.75rem)";

export interface WorkspaceNavProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly items?: readonly WorkspaceNavigationItem[];
  readonly onGoToWorkspaces: () => void;
}

export function WorkspaceNav({ workspace, collapsed, onToggleCollapse, items, onGoToWorkspaces }: WorkspaceNavProps) {
  const navItems = items ?? getWorkspacePrimaryNavigation(workspace);
  const workspaceInitials = getWorkspaceInitials(workspace.name);

  return (
    <aside
      className="hidden h-screen flex-shrink-0 bg-gradient-to-b from-slate-50/80 via-white to-slate-50/60 px-3 py-4 transition-[width] duration-200 ease-out lg:flex"
      style={{ width: collapsed ? COLLAPSED_NAV_WIDTH : EXPANDED_NAV_WIDTH }}
      aria-label="Primary workspace navigation"
      aria-expanded={!collapsed}
    >
      <div
        className={clsx(
          "flex h-full w-full flex-col rounded-[1.7rem] border border-white/70 bg-white/90 shadow-[0_25px_60px_-40px_rgba(15,23,42,0.7)] ring-1 ring-slate-100/60 backdrop-blur-sm",
          collapsed ? "items-center gap-4 px-2 py-5" : "gap-5 px-4 py-6",
        )}
      >
        <div
          className={clsx(
            "flex w-full items-center gap-3 rounded-2xl border border-white/80 bg-gradient-to-r from-slate-50 via-white to-slate-50 px-3 py-4 text-sm font-semibold text-slate-700 shadow-inner shadow-white/60",
            collapsed ? "flex-col text-center text-xs" : "",
          )}
        >
          <button
            type="button"
            onClick={onGoToWorkspaces}
            className="flex flex-1 items-center gap-3 text-left"
          >
            <span
              className={clsx(
                "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold uppercase text-white shadow-[0_10px_25px_-10px_rgba(79,70,229,0.7)]",
                collapsed && "h-9 w-9 text-xs",
              )}
            >
              {workspaceInitials}
            </span>
            {collapsed ? (
              <span className="sr-only">{workspace.name}</span>
            ) : (
              <div className="min-w-0">
                <p className="truncate">{workspace.name}</p>
                <p className="text-xs font-normal text-slate-500">Switch workspace</p>
              </div>
            )}
          </button>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-transparent text-slate-500 hover:border-brand-200 hover:text-brand-600"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ExpandIcon /> : <CollapseIcon />}
          </button>
        </div>
        <nav className="mt-4 flex-1 overflow-y-auto pr-1" aria-label="Workspace sections">
          <WorkspaceNavList items={navItems} collapsed={collapsed} />
        </nav>
      </div>
    </aside>
  );
}

interface WorkspaceNavListProps {
  readonly items: readonly WorkspaceNavigationItem[];
  readonly collapsed?: boolean;
  readonly onNavigate?: () => void;
  readonly className?: string;
  readonly showHeading?: boolean;
}

export function WorkspaceNavList({ items, collapsed = false, onNavigate, className }: WorkspaceNavListProps) {
  return (
    <ul className={clsx("flex flex-col gap-2", collapsed ? "items-center" : undefined, className)} role="list">
      {items.map((item) => (
        <li key={item.id} className="w-full">
          <NavLink
            to={item.href}
            end
            title={collapsed ? item.label : undefined}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "group relative flex w-full items-center rounded-2xl border border-transparent text-sm font-medium text-slate-600 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                collapsed ? "h-12 justify-center px-0" : "gap-3 px-3 py-2.5",
                isActive
                  ? "border-brand-200/80 bg-gradient-to-r from-brand-50 via-white to-brand-50/70 text-brand-800 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]"
                  : "border-transparent bg-transparent hover:border-slate-200 hover:bg-slate-50/60",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  aria-hidden
                  className={clsx(
                    "absolute left-1.5 top-1.5 bottom-1.5 w-1 rounded-full bg-brand-400 transition-opacity",
                    collapsed && "hidden",
                    isActive ? "opacity-100" : "opacity-0 group-hover:opacity-60",
                  )}
                />
                <span
                  className={clsx(
                    "flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition group-hover:bg-slate-100/80",
                    isActive && "bg-white text-brand-700 shadow-inner shadow-brand-200/70",
                    collapsed && "h-10 w-10",
                  )}
                >
                  <item.icon
                    className={clsx("h-5 w-5 flex-shrink-0 transition-colors", isActive ? "text-brand-600" : "text-slate-500")}
                    aria-hidden
                  />
                </span>
                <div className={clsx("flex min-w-0 flex-col text-left", collapsed && "sr-only")}>
                  <span className="truncate text-sm font-semibold text-slate-900">{item.label}</span>
                  <span className="text-xs text-slate-500">Jump to {item.label}</span>
                </div>
              </>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
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
