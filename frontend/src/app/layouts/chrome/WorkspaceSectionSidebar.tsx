import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceSectionDescriptor } from "../../workspaces/sections";
import type { WorkspaceSecondaryNavigation } from "../../workspaces/navigation";

export interface WorkspaceSectionSidebarProps {
  readonly section: WorkspaceSectionDescriptor;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
  readonly navigation: WorkspaceSecondaryNavigation;
}

const COLLAPSED_WIDTH = 72;
const EXPANDED_WIDTH = 280;

export function WorkspaceSectionSidebar({
  section,
  collapsed,
  onToggleCollapse,
  onNavigate,
  navigation,
}: WorkspaceSectionSidebarProps) {

  return (
    <aside
      className="hidden h-full flex-col border-r border-slate-200 bg-white transition-[width,box-shadow] duration-300 ease-out lg:flex"
      style={{ width: collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH }}
      aria-label={`${section.label} navigation`}
      aria-expanded={!collapsed}
    >
      <NavigationHeader label={section.label} collapsed={collapsed} onToggleCollapse={onToggleCollapse} />

      <div className="flex-1 overflow-y-auto px-3 py-4">
        {navigation.status === "loading" ? (
          <LoadingState collapsed={collapsed} message="Loading navigation…" />
        ) : navigation.items.length > 0 ? (
          <nav aria-label={`${section.label} views`}>
            <ul className="flex flex-col gap-1" role="list">
              {navigation.items.map((item) => (
                <li key={item.id}>
                  <NavLink
                    to={item.href}
                    onClick={() => onNavigate?.()}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      clsx(
                        "group flex h-11 items-center rounded-lg text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                        collapsed ? "justify-center px-0" : "justify-between px-3",
                        isActive
                          ? "bg-slate-900 text-white"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span className="flex items-center gap-3">
                          <span
                            className={clsx(
                              "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md text-xs font-semibold uppercase tracking-wide transition",
                              isActive
                                ? "bg-slate-900/90 text-white"
                                : "bg-slate-100 text-slate-500 group-hover:bg-white group-hover:text-brand-600",
                            )}
                            aria-hidden
                          >
                            {item.label.charAt(0)}
                          </span>
                          <span
                            className={clsx(
                              "min-w-0 truncate transition-[opacity,transform] duration-150 ease-out",
                              collapsed ? "pointer-events-none opacity-0 -translate-x-3" : "opacity-100 translate-x-0",
                            )}
                          >
                            {item.label}
                          </span>
                        </span>
                        {item.badge ? <Badge collapsed={collapsed}>{item.badge}</Badge> : null}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        ) : (
          <EmptyState collapsed={collapsed} message={navigation.emptyLabel} />
        )}
      </div>
    </aside>
  );
}

function NavigationHeader({
  label,
  collapsed,
  onToggleCollapse,
}: {
  readonly label: string;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
}) {
  return (
    <div className="flex h-14 items-center justify-between border-b border-slate-200 px-3">
      <div
        className={clsx(
          "rounded-md px-2 text-[0.68rem] font-semibold uppercase tracking-wide text-slate-400 transition-[opacity,transform] duration-200",
          collapsed ? "pointer-events-none opacity-0 -translate-x-2" : "opacity-100 translate-x-0",
        )}
      >
        {label}
      </div>
      <button
        type="button"
        onClick={onToggleCollapse}
        className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label={collapsed ? "Expand section navigation" : "Collapse section navigation"}
        aria-pressed={collapsed}
      >
        <CollapseIcon collapsed={collapsed} />
      </button>
    </div>
  );
}

function Badge({ collapsed, children }: { readonly collapsed: boolean; readonly children: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500 transition-opacity duration-200",
        collapsed ? "opacity-0" : "opacity-100",
      )}
    >
      {children}
    </span>
  );
}

function EmptyState({ collapsed, message }: { readonly collapsed: boolean; readonly message: string }) {
  return (
    <div className="flex h-full items-center justify-center px-3 text-center text-sm text-slate-400">
      <p className={clsx(collapsed && "sr-only")}>{message}</p>
    </div>
  );
}

function LoadingState({ collapsed, message }: { readonly collapsed: boolean; readonly message: string }) {
  return (
    <div className="flex flex-col gap-2 px-1 py-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          // eslint-disable-next-line react/no-array-index-key
          key={index}
          className={clsx(
            "h-10 rounded-lg bg-slate-100/70",
            collapsed ? "mx-auto w-10" : "animate-pulse",
          )}
        />
      ))}
      <p className={clsx("px-3 text-center text-xs text-slate-400", collapsed && "sr-only")}>{message}</p>
    </div>
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
