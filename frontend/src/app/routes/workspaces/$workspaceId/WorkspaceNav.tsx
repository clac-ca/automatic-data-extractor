import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceProfile } from "@types/workspaces";
import { getWorkspacePrimaryNavigation } from "./sections";

export interface WorkspaceNavProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
}

export function WorkspaceNav({ workspace, collapsed, onToggleCollapse }: WorkspaceNavProps) {
  const items = getWorkspacePrimaryNavigation(workspace);

  return (
    <aside
      className="hidden h-full flex-shrink-0 border-r border-slate-200 bg-white transition-[width] duration-200 ease-out lg:block"
      style={{ width: collapsed ? "4.5rem" : "15rem" }}
      aria-label="Primary workspace navigation"
      aria-expanded={!collapsed}
    >
      <div className={clsx("flex h-full flex-col", collapsed ? "items-center" : "items-stretch")}>
        <div className={clsx("flex items-center justify-end px-2 py-3", collapsed ? "w-full justify-center" : undefined)}>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-600"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ExpandIcon /> : <CollapseIcon />}
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-4" aria-label="Workspace sections">
          <ul className={clsx("flex flex-col gap-1", collapsed ? "items-center" : undefined)} role="list">
            {items.map((item) => (
              <li key={item.id} className={collapsed ? "w-full" : undefined}>
                <NavLink
                  to={item.href}
                  end
                  className={({ isActive }) =>
                    clsx(
                      "flex h-11 items-center rounded-lg text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                      collapsed ? "w-11 justify-center" : "gap-3 px-3",
                      isActive
                        ? "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
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
