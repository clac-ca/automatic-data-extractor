import { useMemo } from "react";
import { NavLink } from "react-router-dom";

import type { WorkspaceProfile } from "../../../shared/api/types";
import { formatRoleList } from "../utils/roles";
import { useWorkspaceChrome } from "./WorkspaceChromeContext";

interface WorkspaceRailLink {
  id: string;
  label: string;
  href: string;
  end?: boolean;
}

interface WorkspaceRailProps {
  workspaces: WorkspaceProfile[];
  activeWorkspaceId?: string;
  onSelectWorkspace: (workspaceId: string) => void;
  navigationItems: WorkspaceRailLink[];
  canCreateWorkspaces: boolean;
  onCreateWorkspace: () => void;
}

function getInitials(name: string) {
  const trimmed = name.trim();
  if (!trimmed) {
    return "?";
  }

  const parts = trimmed.split(/\s+/).slice(0, 2);
  return parts
    .map((part) => part[0] ?? "")
    .join("")
    .toUpperCase();
}

export function WorkspaceRail({
  workspaces,
  activeWorkspaceId,
  onSelectWorkspace,
  navigationItems,
  canCreateWorkspaces,
  onCreateWorkspace,
}: WorkspaceRailProps) {
  const { isDesktop, isRailCollapsed, closeOverlay } = useWorkspaceChrome();
  const isCondensed = isDesktop && isRailCollapsed;
  const showNavigation = navigationItems.length > 1 && !!activeWorkspaceId;

  const workspaceEntries = useMemo(() => workspaces.map((workspace) => ({
    id: workspace.id,
    name: workspace.name,
    subtitle: [formatRoleList(workspace.roles), workspace.slug, workspace.is_default ? "Default" : null]
      .filter(Boolean)
      .join(" • "),
  })), [workspaces]);

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className={isCondensed ? "flex flex-col items-center gap-3 px-2 py-6" : "px-4 py-6"}>
        <h2 className={isCondensed ? "sr-only" : "text-sm font-semibold text-slate-200"}>Workspaces</h2>
        <ul className={isCondensed ? "flex flex-col items-center gap-2" : "mt-2 space-y-1 text-sm"}>
          {canCreateWorkspaces ? (
            <li className={isCondensed ? "mb-3" : "mb-4"}>
              <button
                type="button"
                onClick={() => {
                  closeOverlay();
                  onCreateWorkspace();
                }}
                className={
                  isCondensed
                    ? "flex h-12 w-12 items-center justify-center rounded-full border border-dashed border-sky-500/60 bg-slate-950 text-lg font-semibold text-sky-200 transition hover:border-sky-400 hover:text-sky-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                    : "flex w-full items-center justify-center gap-2 rounded border border-dashed border-sky-500/60 px-3 py-2 text-sm font-semibold text-sky-200 transition hover:border-sky-400 hover:text-sky-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                }
                aria-label="New workspace"
              >
                <span aria-hidden className="text-base">+</span>
                {!isCondensed ? <span>New workspace</span> : <span className="sr-only">New workspace</span>}
              </button>
            </li>
          ) : null}
          {workspaceEntries.map((entry) => {
            const isActive = entry.id === activeWorkspaceId;
            const baseClass =
              "flex w-full items-center gap-3 rounded transition focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";
            const stateClass = isActive
              ? "bg-slate-900 text-slate-50"
              : "text-slate-400 hover:bg-slate-900/70 hover:text-slate-100";

            if (isCondensed) {
              return (
                <li key={entry.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelectWorkspace(entry.id);
                      closeOverlay();
                    }}
                    className={`${baseClass} h-12 w-12 justify-center rounded-full border border-slate-800 bg-slate-950 text-sm font-semibold`}
                    aria-label={entry.name}
                  >
                    {getInitials(entry.name)}
                  </button>
                </li>
              );
            }

            return (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => {
                    onSelectWorkspace(entry.id);
                    closeOverlay();
                  }}
                  className={`${baseClass} px-3 py-2 text-left ${stateClass}`}
                >
                  <div className="flex flex-col">
                    <span className="font-medium text-slate-100">{entry.name}</span>
                    {entry.subtitle ? <span className="text-xs text-slate-500">{entry.subtitle}</span> : null}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      {showNavigation ? (
        <nav aria-label="Workspace sections" className="mt-auto border-t border-slate-900 px-2 py-4 text-sm text-slate-400">
          <ul className={isCondensed ? "flex flex-col items-center gap-2" : "space-y-1"}>
            {navigationItems.map((item) => (
              <li key={item.id} className="w-full">
                <NavLink
                  to={item.href}
                  end={item.end}
                  onClick={() => closeOverlay()}
                  className={({ isActive }) => {
                    const activeClass = isActive ? "bg-sky-500/20 text-sky-200" : "hover:bg-slate-900/70 hover:text-slate-100";
                    const base =
                      "flex items-center gap-3 rounded px-3 py-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";
                    return `${base} ${activeClass} ${isCondensed ? "justify-center" : ""}`;
                  }}
                  title={item.label}
                >
                  {isCondensed ? <span className="sr-only">{item.label}</span> : item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </div>
  );
}
