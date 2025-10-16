import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceSectionDescriptor } from "../../workspaces/sections";
import { getWorkspaceSecondaryNavItems } from "../../workspaces/navigation";

export interface WorkspaceSectionSidebarProps {
  readonly workspaceId: string;
  readonly section: WorkspaceSectionDescriptor;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
}

const COLLAPSED_WIDTH = 80;
const EXPANDED_WIDTH = 256;

export function WorkspaceSectionSidebar({
  workspaceId,
  section,
  collapsed,
  onToggleCollapse,
  onNavigate,
}: WorkspaceSectionSidebarProps) {
  const items = getWorkspaceSecondaryNavItems(workspaceId, section);

  return (
    <aside
      className="hidden h-full flex-col border-r border-slate-200 bg-white/90 backdrop-blur transition-[width,box-shadow] duration-300 ease-out lg:flex"
      style={{ width: collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH }}
      aria-label={`${section.label} navigation`}
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div
          className={clsx(
            "text-xs font-semibold uppercase tracking-wide text-slate-400 transition-[opacity,transform] duration-200",
            collapsed ? "pointer-events-none opacity-0 -translate-x-2" : "opacity-100 translate-x-0",
          )}
        >
          {section.label}
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
          aria-label={collapsed ? "Expand section navigation" : "Collapse section navigation"}
          aria-pressed={collapsed}
        >
          <CollapseIcon collapsed={collapsed} />
        </button>
      </div>

      {items.length > 0 ? (
        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label={`${section.label} views`}>
          <ul className="flex flex-col gap-1" role="list">
            {items.map((item) => (
              <li key={item.id}>
                <NavLink
                  to={item.href}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    clsx(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                      isActive ? "bg-slate-100 text-slate-900" : "text-slate-600 hover:bg-slate-100",
                      collapsed ? "justify-center" : "justify-between",
                    )
                  }
                  title={item.label}
                >
                  <span className="flex items-center gap-3">
                    <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs font-semibold text-slate-500">
                      {item.label.charAt(0).toUpperCase()}
                    </span>
                    <span
                      className={clsx(
                        "flex min-w-0 flex-1 flex-col overflow-hidden text-left transition-[opacity,transform] duration-200 ease-out",
                        collapsed ? "pointer-events-none opacity-0 -translate-x-3" : "opacity-100 translate-x-0",
                      )}
                    >
                      <span className="truncate">{item.label}</span>
                    </span>
                  </span>
                  {item.badge ? (
                    <span
                      className={clsx(
                        "inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500 transition-opacity duration-200",
                        collapsed ? "opacity-0" : "opacity-100",
                      )}
                    >
                      {item.badge}
                    </span>
                  ) : null}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      ) : (
        <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-slate-400">
          <p className={clsx(collapsed && "sr-only")}>
            No saved views for this section yet.
          </p>
        </div>
      )}
    </aside>
  );
}

function CollapseIcon({ collapsed }: { readonly collapsed: boolean }) {
  return collapsed ? (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 4h12v12H4z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9 10l-2 2m2-2l-2-2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 4h12v12H4z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11 10l2-2m-2 2l2 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
