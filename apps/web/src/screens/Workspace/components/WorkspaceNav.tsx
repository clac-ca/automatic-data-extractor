import { NavLink } from "@app/nav/Link";
import clsx from "clsx";

import { getWorkspacePrimaryNavigation, type WorkspaceNavigationItem } from "@screens/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";

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
      className="hidden h-full flex-shrink-0 border-r border-white/70 bg-white/85 pb-4 pt-2 shadow-[inset_-1px_0_0_rgba(15,23,42,0.04)] backdrop-blur supports-[backdrop-filter]:backdrop-blur-xl transition-[width] duration-200 ease-out lg:flex"
      style={{ width: collapsed ? "4.5rem" : "16.25rem" }}
      aria-label="Primary workspace navigation"
      aria-expanded={!collapsed}
    >
      <div className={clsx("flex h-full w-full flex-col", collapsed ? "items-center" : "items-stretch")}>
        <div className={clsx("flex w-full items-center px-3 py-3", collapsed ? "justify-center" : "justify-between")}>
          {!collapsed ? (
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Workspace</p>
          ) : (
            <span className="sr-only">Workspace navigation</span>
          )}
          <button
            type="button"
            onClick={onToggleCollapse}
            className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/60 bg-white/80 text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-600"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ExpandIcon /> : <CollapseIcon />}
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-2" aria-label="Workspace sections">
          <ul className={clsx("flex flex-col gap-1", collapsed ? "items-center" : undefined)} role="list">
            {navItems.map((item) => (
              <li key={item.id} className={collapsed ? "w-full" : undefined}>
                <NavLink
                  to={item.href}
                  end
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    clsx(
                      "flex h-11 items-center rounded-xl border border-transparent text-sm font-medium text-slate-500 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                      collapsed ? "w-12 justify-center" : "gap-3 px-3",
                      isActive
                        ? "border-brand-200 bg-brand-50 text-brand-700 shadow-[0_8px_20px_-16px_rgba(79,70,229,0.8)]"
                        : "hover:border-slate-200/80 hover:bg-white hover:text-slate-900",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon
                        className={clsx(
                          "h-5 w-5 flex-shrink-0 transition-colors",
                          isActive ? "text-brand-600" : "text-slate-400",
                        )}
                        aria-hidden
                      />
                      <span className={clsx("truncate", collapsed && "sr-only")}>{item.label}</span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </aside>
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
