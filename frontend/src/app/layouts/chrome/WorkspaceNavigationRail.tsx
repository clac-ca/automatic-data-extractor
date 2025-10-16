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
const EXPANDED_WIDTH = 248;

export function WorkspaceNavigationRail({
  workspace,
  collapsed,
  onToggleCollapse,
  onNavigate,
}: WorkspaceNavigationRailProps) {
  const items = getWorkspacePrimaryNavItems(workspace);

  return (
    <aside
      className={clsx(
        "hidden h-full flex-col border-r border-slate-200 bg-white/95 transition-[width,box-shadow] duration-300 ease-out lg:flex",
        collapsed
          ? "shadow-[inset_-1px_0_0_rgba(15,23,42,0.08)]"
          : "shadow-[0_12px_32px_-18px_rgba(15,23,42,0.4)]",
      )}
      style={{ width: collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH }}
      aria-label="Primary navigation"
    >
      <nav className="flex-1 overflow-y-auto px-3 py-6" aria-label="Workspace sections">
        <ul className="flex flex-col gap-1" role="list">
          {items.map((item) => (
            <li key={item.id}>
              <NavLink
                to={item.href}
                onClick={onNavigate}
                className={({ isActive }) =>
                  clsx(
                    "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                    isActive
                      ? "bg-brand-50 text-brand-700 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.25)]"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                    collapsed ? "justify-center" : "justify-start",
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
                  <span className="truncate">{item.label}</span>
                  <span className="truncate text-xs font-normal text-slate-400">{item.description}</span>
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="px-3 pb-5">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="focus-ring group flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
          aria-pressed={collapsed}
          aria-label={collapsed ? "Expand primary navigation" : "Collapse primary navigation"}
        >
          <CollapseIcon collapsed={collapsed} />
          {collapsed ? null : <span className="transition-opacity duration-200">Collapse</span>}
        </button>
      </div>
    </aside>
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
