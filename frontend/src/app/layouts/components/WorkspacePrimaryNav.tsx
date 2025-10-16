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

interface WorkspacePrimaryNavProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onCloseDrawer?: () => void;
  readonly className?: string;
}

interface PrimaryNavItem {
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly icon: ReactNode;
  readonly href: string;
}

export function WorkspacePrimaryNav({ workspace, collapsed, onCloseDrawer, className }: WorkspacePrimaryNavProps) {
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
        "flex h-full flex-col border-r border-slate-200 bg-white/95 backdrop-blur md:bg-white",
        className,
      )}
      aria-label="Workspace sections"
    >
      <ul className="flex-1 space-y-1 px-3 py-4">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                  collapsed && "justify-center px-2 py-2",
                )
              }
              onClick={onCloseDrawer}
            >
              <span
                className={clsx(
                  "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border transition",
                  "border-transparent bg-slate-100 text-slate-500 group-hover:bg-white group-hover:text-brand-600",
                )}
              >
                {item.icon}
              </span>
              {!collapsed ? (
                <span className="flex min-w-0 flex-col text-left">
                  <span className="truncate">{item.label}</span>
                  <span className="truncate text-xs font-normal text-slate-400">{item.description}</span>
                </span>
              ) : null}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
