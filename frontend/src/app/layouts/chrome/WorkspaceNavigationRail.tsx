import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import { getWorkspacePrimaryNavItems } from "../../workspaces/navigation";
import { NavigationSurfaceHeader } from "./NavigationSurfaceHeader";

export interface WorkspaceNavigationRailProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
}

const COLLAPSED_WIDTH = 72;
const EXPANDED_WIDTH = 272;

export function WorkspaceNavigationRail({
  workspace,
  collapsed,
  onToggleCollapse,
  onNavigate,
}: WorkspaceNavigationRailProps) {
  const items = getWorkspacePrimaryNavItems(workspace);

  return (
    <aside
      className="hidden h-full flex-col border-r border-slate-200 bg-white transition-[width,box-shadow] duration-300 ease-out lg:flex"
      style={{ width: collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH }}
      aria-label="Primary navigation"
      aria-expanded={!collapsed}
    >
      <NavigationSurfaceHeader
        label="Workspace"
        collapsed={collapsed}
        onToggleCollapse={onToggleCollapse}
        collapseLabel="Collapse primary navigation"
        expandLabel="Expand primary navigation"
      />
      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Workspace sections">
        <ul className="flex flex-col gap-1" role="list">
          {items.map((item) => (
            <li key={item.id}>
              <NavLink
                to={item.href}
                onClick={() => onNavigate?.()}
                className={({ isActive }) =>
                  clsx(
                    "group flex h-11 items-center gap-3 rounded-lg text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                    collapsed ? "justify-center px-0" : "justify-start px-3",
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  )
                }
                title={collapsed ? item.label : undefined}
              >
                {({ isActive }) => (
                  <>
                    <item.icon
                      className={clsx(
                        "h-5 w-5 flex-shrink-0 transition-colors",
                        isActive ? "text-white" : "text-slate-500 group-hover:text-brand-600",
                      )}
                      aria-hidden
                    />
                    <span
                      className={clsx(
                        "min-w-0 truncate transition-[opacity,transform] duration-150 ease-out",
                        collapsed ? "sr-only" : "opacity-100 translate-x-0",
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
      </nav>
    </aside>
  );
}
