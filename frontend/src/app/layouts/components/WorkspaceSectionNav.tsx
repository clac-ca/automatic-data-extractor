import { useMemo } from "react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceSectionDescriptor } from "../../workspaces/sections";

interface WorkspaceSectionNavProps {
  readonly workspaceId: string;
  readonly section: WorkspaceSectionDescriptor;
  readonly className?: string;
  readonly onCloseDrawer?: () => void;
}

interface SectionNavItem {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly badge?: string;
}

export function WorkspaceSectionNav({ workspaceId, section, className, onCloseDrawer }: WorkspaceSectionNavProps) {
  const items = useMemo<SectionNavItem[]>(() => getSectionNavItems(workspaceId, section.id), [section.id, workspaceId]);

  if (items.length === 0) {
    return (
      <aside
        className={clsx(
          "hidden w-64 flex-shrink-0 border-r border-slate-200 bg-white/80 px-4 py-6 text-sm text-slate-400 lg:flex",
          className,
        )}
        aria-label={`${section.label} views`}
      >
        <p>No saved views for this section yet.</p>
      </aside>
    );
  }

  return (
    <nav
      className={clsx(
        "hidden w-64 flex-shrink-0 border-r border-slate-200 bg-white/90 px-4 py-6 shadow-[0_1px_2px_rgba(15,23,42,0.08)] lg:flex",
        className,
      )}
      aria-label={`${section.label} views`}
    >
      <ul className="space-y-1 w-full">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  "flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                )
              }
              onClick={onCloseDrawer}
            >
              <span>{item.label}</span>
              {item.badge ? (
                <span className="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500">
                  {item.badge}
                </span>
              ) : null}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
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
