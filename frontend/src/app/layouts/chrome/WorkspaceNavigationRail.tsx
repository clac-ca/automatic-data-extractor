import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import { getWorkspacePrimaryNavItems } from "../../workspaces/navigation";

export interface WorkspaceNavigationRailProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
}

const COLLAPSED_WIDTH = 72;
const EXPANDED_WIDTH = 280;

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
    >
      <RailHeader collapsed={collapsed} onToggleCollapse={onToggleCollapse} />
      <nav className="flex-1 overflow-y-auto px-2 py-4" aria-label="Workspace sections">
        <ul className="flex flex-col gap-1" role="list">
          {items.map((item) => (
            <li key={item.id}>
              <NavLink
                to={item.href}
                onClick={onNavigate}
                className={({ isActive }) =>
                  clsx(
                    "group relative flex h-11 items-center gap-3 rounded-lg text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                    collapsed ? "justify-center px-0" : "px-3 justify-start",
                    isActive
                      ? "bg-brand-50 text-brand-700 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.15)]"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  )
                }
                title={item.label}
              >
                <span
                  className={clsx(
                    "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-transparent bg-slate-100 text-slate-500 transition group-hover:bg-white group-hover:text-brand-600",
                    collapsed ? "shadow-none" : "shadow-sm",
                  )}
                  aria-hidden
                >
                  <item.icon className="h-5 w-5" />
                </span>
                <span
                  className={clsx(
                    "flex min-w-0 flex-col overflow-hidden text-left transition-[opacity,transform] duration-200 ease-out",
                    collapsed ? "pointer-events-none opacity-0 -translate-x-3" : "opacity-100 translate-x-0",
                  )}
                >
                  <span className="truncate text-sm font-semibold">{item.label}</span>
                  <span className="truncate text-xs font-normal text-slate-400">{item.description}</span>
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}

function RailHeader({
  collapsed,
  onToggleCollapse,
}: {
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
}) {
  return (
    <div className="flex h-16 items-center justify-between border-b border-slate-200 px-2">
      <div
        className={clsx(
          "rounded-md px-2 text-[0.7rem] font-semibold uppercase tracking-wide text-slate-400 transition-[opacity,transform] duration-200",
          collapsed ? "pointer-events-none opacity-0 -translate-x-2" : "opacity-100 translate-x-0",
        )}
      >
        Workspace
      </div>
      <button
        type="button"
        onClick={onToggleCollapse}
        className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label={collapsed ? "Expand primary navigation" : "Collapse primary navigation"}
        aria-pressed={collapsed}
      >
        <CollapseIcon collapsed={collapsed} />
      </button>
    </div>
  );
}

function CollapseIcon({ collapsed }: { readonly collapsed: boolean }) {
  return collapsed ? (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M3 4h14v12H3z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 10l-2 2m2-2l-2-2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M3 4h14v12H3z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 10l2-2m-2 2l2 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
