import { useMemo } from "react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";

import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import { buildWorkspaceSectionPath } from "../../workspaces/sections";
import {
  DocumentsIcon,
  OverviewIcon,
  RunsIcon,
  DataIcon,
  ConfigureIcon,
  SettingsIcon,
} from "../../workspaces/icons";

interface PrimaryNavItem {
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly icon: ReactNode;
  readonly href: string;
}

export interface WorkspacePrimaryNavProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onNavigate?: () => void;
  readonly className?: string;
  readonly animatedWidth?: boolean;
}

export function WorkspacePrimaryNav({
  workspace,
  collapsed,
  onToggleCollapse,
  onNavigate,
  className,
  animatedWidth = true,
}: WorkspacePrimaryNavProps) {
  const items = useMemo<PrimaryNavItem[]>(
    () => [
      {
        id: "documents",
        label: "Documents",
        description: "Uploads and extraction runs",
        icon: <DocumentsIcon className="h-5 w-5" />,
        href: buildWorkspaceSectionPath(workspace.id, "documents"),
      },
      {
        id: "overview",
        label: "Overview",
        description: "Workspace health and metrics",
        icon: <OverviewIcon className="h-5 w-5" />,
        href: buildWorkspaceSectionPath(workspace.id, "overview"),
      },
      {
        id: "runs",
        label: "Runs & Jobs",
        description: "Processing history and monitoring",
        icon: <RunsIcon className="h-5 w-5" />,
        href: buildWorkspaceSectionPath(workspace.id, "runs"),
      },
      {
        id: "data",
        label: "Data",
        description: "Datasets, exports, and records",
        icon: <DataIcon className="h-5 w-5" />,
        href: buildWorkspaceSectionPath(workspace.id, "data"),
      },
      {
        id: "config",
        label: "Configure",
        description: "Pipelines, rules, automations",
        icon: <ConfigureIcon className="h-5 w-5" />,
        href: buildWorkspaceSectionPath(workspace.id, "config"),
      },
      {
        id: "settings",
        label: "Settings",
        description: "Workspace preferences & access",
        icon: <SettingsIcon className="h-5 w-5" />,
        href: buildWorkspaceSectionPath(workspace.id, "settings"),
      },
    ],
    [workspace.id],
  );

  return (
    <nav
      className={clsx(
        "flex h-full flex-col border-r border-slate-200 bg-white/95 backdrop-blur transition-[width] duration-300 ease-in-out",
        collapsed ? "shadow-[inset_-1px_0_0_rgba(15,23,42,0.06)]" : "shadow-[0_1px_2px_rgba(15,23,42,0.08)]",
        className,
      )}
      style={animatedWidth ? { width: collapsed ? "4.5rem" : "17rem" } : undefined}
      aria-label="Workspace sections"
    >
      <ul className="flex-1 space-y-1 px-3 py-4">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  "group flex items-center gap-3 rounded-xl px-2 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                  collapsed && "justify-center",
                )
              }
              title={item.label}
              onClick={onNavigate}
            >
              <span
                className={clsx(
                  "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-transparent bg-slate-100 text-slate-500 transition group-hover:bg-white group-hover:text-brand-600",
                  collapsed ? "shadow-none" : "shadow-sm",
                )}
                aria-hidden="true"
              >
                {item.icon}
              </span>
              <span
                className={clsx(
                  "flex min-w-0 flex-col overflow-hidden text-left transition-[opacity,transform] duration-200 ease-out",
                  collapsed ? "pointer-events-none opacity-0 -translate-x-3" : "opacity-100 translate-x-0",
                )}
                aria-hidden={collapsed}
              >
                <span className="truncate">{item.label}</span>
                <span className="truncate text-xs font-normal text-slate-400">{item.description}</span>
              </span>
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-slate-200 px-3 py-4">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="focus-ring group flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
          aria-pressed={collapsed}
          aria-label={collapsed ? "Expand primary navigation" : "Collapse primary navigation"}
        >
          <CollapseIcon collapsed={collapsed} />
          {!collapsed ? (
            <span className="transition-opacity duration-200">Collapse</span>
          ) : null}
        </button>
      </div>
    </nav>
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
