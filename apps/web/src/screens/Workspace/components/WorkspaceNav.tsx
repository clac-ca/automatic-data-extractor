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
}

export function WorkspaceNav({ workspace, collapsed, onToggleCollapse, items }: WorkspaceNavProps) {
  const navItems = items ?? getWorkspacePrimaryNavigation(workspace);

  return (
    <aside
      className="hidden h-full flex-shrink-0 transition-[width] duration-200 ease-out lg:flex"
      style={{ width: collapsed ? COLLAPSED_NAV_WIDTH : EXPANDED_NAV_WIDTH }}
      aria-label="Primary workspace navigation"
      aria-expanded={!collapsed}
    >
      <div
        className={clsx(
          "flex h-full w-full flex-col rounded-r-3xl border-r border-slate-100/60 bg-gradient-to-b from-white via-slate-50 to-white/90 py-4 shadow-[0_25px_60px_-40px_rgba(15,23,42,0.65)] backdrop-blur supports-[backdrop-filter]:backdrop-blur-lg",
          collapsed ? "items-center px-3" : "items-stretch px-5",
        )}
      >
        <div
          className={clsx(
            "flex w-full items-center gap-3 rounded-2xl border border-white/70 bg-white/80 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 shadow-sm",
            collapsed ? "justify-center" : "justify-between",
          )}
        >
          {!collapsed ? <span>Workspace</span> : <span className="sr-only">Workspace navigation</span>}
          <button
            type="button"
            onClick={onToggleCollapse}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500 transition hover:border-brand-200 hover:text-brand-600"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ExpandIcon /> : <CollapseIcon />}
          </button>
        </div>
        <nav className="mt-6 flex-1 overflow-y-auto" aria-label="Workspace sections">
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
  readonly headingLabel?: string;
  readonly showHeading?: boolean;
}

export function WorkspaceNavList({
  items,
  collapsed = false,
  onNavigate,
  className,
  headingLabel = "Workspace",
  showHeading = true,
}: WorkspaceNavListProps) {
  return (
    <div className={clsx("flex flex-col gap-3", className)}>
      {showHeading ? (
        <div className={clsx("px-1 text-xs font-semibold uppercase tracking-wide text-slate-400", collapsed && "sr-only")}>
          {headingLabel}
        </div>
      ) : null}
      <ul className={clsx("flex flex-col gap-2", collapsed ? "items-center" : undefined)} role="list">
        {items.map((item) => (
          <li key={item.id} className={collapsed ? "w-full" : undefined}>
            <NavLink
              to={item.href}
              end
              title={collapsed ? item.label : undefined}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  "group flex items-center rounded-2xl border border-transparent text-sm font-medium text-slate-600 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  collapsed ? "h-12 w-12 justify-center" : "gap-4 px-3 py-2.5",
                  isActive
                    ? "border-brand-200/80 bg-brand-50/60 text-brand-800 shadow-[0_20px_45px_-25px_rgba(79,70,229,0.65)]"
                    : "border-slate-100/80 bg-white/80 shadow-[0_18px_35px_-30px_rgba(15,23,42,0.45)] hover:border-slate-200/70 hover:bg-white",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={clsx(
                      "flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition group-hover:bg-slate-100/80",
                      isActive && "bg-white text-brand-700 shadow-inner shadow-brand-200/70",
                      collapsed && "h-11 w-11",
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
    </div>
  );
}

function CollapseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M12 5h3v3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 15H5v-3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 5l-9 9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ExpandIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M8 5H5v3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 15h3v-3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 8l9 9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
