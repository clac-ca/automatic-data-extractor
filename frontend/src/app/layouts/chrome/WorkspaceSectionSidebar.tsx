import { useId } from "react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceSectionDescriptor } from "../../workspaces/sections";
import type { WorkspaceSecondaryNavigation } from "../../workspaces/navigation";
import { NavigationSurfaceHeader } from "./NavigationSurfaceHeader";
import { NAV_SURFACE_COLLAPSED_WIDTH, NAV_SURFACE_EXPANDED_WIDTH } from "./navigationSurface";

export interface WorkspaceSectionSidebarProps {
  readonly section: WorkspaceSectionDescriptor;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
  readonly navigation: WorkspaceSecondaryNavigation;
}

export function WorkspaceSectionSidebar({
  section,
  collapsed,
  onToggleCollapse,
  onNavigate,
  navigation,
}: WorkspaceSectionSidebarProps) {
  const navId = useId();
  const headingId = `${navId}-label`;

  return (
    <aside
      className="hidden h-full flex-col border-r border-slate-200 bg-white transition-[width,box-shadow] duration-300 ease-out lg:flex"
      style={{ width: collapsed ? NAV_SURFACE_COLLAPSED_WIDTH : NAV_SURFACE_EXPANDED_WIDTH }}
      aria-label={`${section.label} navigation`}
      aria-expanded={!collapsed}
      aria-labelledby={headingId}
    >
      <NavigationSurfaceHeader
        label={section.label}
        collapsed={collapsed}
        onToggleCollapse={onToggleCollapse}
        collapseLabel="Collapse section navigation"
        expandLabel="Expand section navigation"
        controlsId={navId}
        headingId={headingId}
      />

      <div id={navId} className="flex-1 overflow-y-auto px-3 py-4">
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
                    className={({ isActive }) =>
                      clsx(
                        "group flex h-11 items-center rounded-lg text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                        collapsed ? "justify-center gap-0 px-0" : "justify-between gap-3 px-3",
                        isActive
                          ? "bg-brand-600 text-white shadow-sm"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                      )
                    }
                    title={collapsed ? item.label : undefined}
                  >
                    {({ isActive }) => (
                      <>
                        <div
                          className={clsx(
                            "flex min-w-0 flex-1 items-center",
                            collapsed ? "w-full justify-center" : "gap-3",
                          )}
                        >
                          {collapsed ? (
                            <span
                              className={clsx(
                                "flex h-9 w-9 items-center justify-center rounded-md text-sm font-semibold uppercase transition",
                                isActive
                                  ? "bg-brand-600 text-white"
                                  : "text-slate-500 group-hover:text-brand-600",
                              )}
                              aria-hidden
                            >
                              {item.label.charAt(0)}
                            </span>
                          ) : null}
                          <span
                            className={clsx(
                              "min-w-0 truncate transition-[opacity,transform] duration-150 ease-out",
                              collapsed ? "sr-only" : "opacity-100 translate-x-0",
                            )}
                          >
                            {item.label}
                          </span>
                        </div>
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

function Badge({ collapsed, children }: { readonly collapsed: boolean; readonly children: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500 transition-opacity duration-200",
        collapsed ? "sr-only" : "opacity-100",
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

