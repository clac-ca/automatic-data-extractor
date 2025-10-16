import { useMemo } from "react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceSectionDescriptor } from "../../workspaces/sections";

interface SectionNavItem {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly badge?: string;
}

export interface WorkspaceSectionNavProps {
  readonly workspaceId: string;
  readonly section: WorkspaceSectionDescriptor;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
  readonly className?: string;
  readonly animatedWidth?: boolean;
}

export function WorkspaceSectionNav({
  workspaceId,
  section,
  collapsed,
  onToggleCollapse,
  onNavigate,
  className,
  animatedWidth = true,
}: WorkspaceSectionNavProps) {
  const items = useMemo<SectionNavItem[]>(() => getSectionNavItems(workspaceId, section.id), [section.id, workspaceId]);

  const containerClass = clsx(
    "flex h-full flex-col border-r border-slate-200 bg-white/90 transition-[width] duration-300 ease-in-out",
    className,
  );

  const width = collapsed ? "4.5rem" : "16rem";

  if (items.length === 0) {
    return (
      <aside className={containerClass} style={animatedWidth ? { width } : undefined} aria-label={`${section.label} views`}>
        <div className="flex flex-1 flex-col items-center justify-center px-4 text-center text-sm text-slate-400">
          <p className={clsx(collapsed && "sr-only")}>
            No saved views for this section yet.
          </p>
        </div>
        <SectionCollapseButton collapsed={collapsed} onToggle={onToggleCollapse} />
      </aside>
    );
  }

  return (
    <nav className={containerClass} style={animatedWidth ? { width } : undefined} aria-label={`${section.label} views`}>
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <span
            className={clsx(
              "text-xs font-semibold uppercase tracking-wide text-slate-400 transition-[opacity,transform] duration-200",
              collapsed ? "pointer-events-none opacity-0 -translate-x-2" : "opacity-100 translate-x-0",
            )}
            aria-hidden={collapsed}
          >
            {section.label}
          </span>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
            aria-label={collapsed ? "Expand section navigation" : "Collapse section navigation"}
            aria-pressed={collapsed}
          >
            <SectionCollapseIcon collapsed={collapsed} />
          </button>
        </div>
      </div>
      <ul className="flex-1 space-y-1 px-3 py-4">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  "group flex items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                  collapsed && "justify-center",
                )
              }
              aria-label={item.label}
              onClick={onNavigate}
            >
              <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs font-semibold text-slate-500">
                {item.label.charAt(0).toUpperCase()}
              </span>
              <span
                className={clsx(
                  "flex min-w-0 flex-1 items-center justify-between gap-2 overflow-hidden transition-[opacity,transform] duration-200 ease-out",
                  collapsed ? "pointer-events-none opacity-0 -translate-x-3" : "opacity-100 translate-x-0",
                )}
                aria-hidden={collapsed}
              >
                <span className="truncate">{item.label}</span>
                {item.badge ? (
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500">
                    {item.badge}
                  </span>
                ) : null}
              </span>
            </NavLink>
          </li>
        ))}
      </ul>
      <SectionCollapseButton collapsed={collapsed} onToggle={onToggleCollapse} />
    </nav>
  );
}

function SectionCollapseButton({
  collapsed,
  onToggle,
}: {
  readonly collapsed: boolean;
  readonly onToggle: () => void;
}) {
  return (
    <div className="border-t border-slate-200 px-3 py-4">
      <button
        type="button"
        onClick={onToggle}
        className="focus-ring inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label={collapsed ? "Expand section navigation" : "Collapse section navigation"}
        aria-pressed={collapsed}
      >
        <SectionCollapseIcon collapsed={collapsed} />
        {!collapsed ? <span>Collapse</span> : null}
      </button>
    </div>
  );
}

function SectionCollapseIcon({ collapsed }: { readonly collapsed: boolean }) {
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

function getSectionNavItems(workspaceId: string, sectionId: WorkspaceSectionDescriptor["id"]): SectionNavItem[] {
  switch (sectionId) {
    case "documents":
      return [
        { id: "documents-inbox", label: "Inbox", href: `/workspaces/${workspaceId}/documents?view=inbox` },
        { id: "documents-processing", label: "Processing", href: `/workspaces/${workspaceId}/documents?view=processing` },
        { id: "documents-completed", label: "Completed", href: `/workspaces/${workspaceId}/documents?view=completed` },
        { id: "documents-failed", label: "Failed", href: `/workspaces/${workspaceId}/documents?view=failed` },
        { id: "documents-archived", label: "Archived", href: `/workspaces/${workspaceId}/documents?view=archived` },
        { id: "documents-saved", label: "Saved filters", href: `/workspaces/${workspaceId}/documents?view=saved` },
      ];
    case "runs":
      return [
        { id: "runs-active", label: "Active jobs", href: `/workspaces/${workspaceId}/runs?view=active` },
        { id: "runs-history", label: "History", href: `/workspaces/${workspaceId}/runs?view=history` },
        { id: "runs-alerts", label: "Alerts", href: `/workspaces/${workspaceId}/runs?view=alerts`, badge: "3" },
      ];
    case "data":
      return [
        { id: "data-datasets", label: "Datasets", href: `/workspaces/${workspaceId}/data?view=datasets` },
        { id: "data-exports", label: "Exports", href: `/workspaces/${workspaceId}/data?view=exports` },
      ];
    default:
      return [];
  }
}
