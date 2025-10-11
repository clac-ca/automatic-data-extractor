import { NavLink } from "react-router-dom";

import type { WorkspaceNavItemConfig } from "../utils/navigation";
import { resolveWorkspaceNavLink } from "../utils/navigation";

interface WorkspaceCanvasNavigationProps {
  items: WorkspaceNavItemConfig[];
  workspaceId?: string;
}

export function WorkspaceCanvasNavigation({ items, workspaceId }: WorkspaceCanvasNavigationProps) {
  if (!workspaceId || items.length <= 1) {
    return null;
  }

  return (
    <nav className="border-b border-slate-900 bg-slate-950/50 px-6 lg:px-8" aria-label="Workspace sections">
      <ul className="flex flex-wrap gap-3 py-3 text-sm text-slate-400">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={resolveWorkspaceNavLink(workspaceId, item.to)}
              end={item.end}
              className={({ isActive }) =>
                `inline-flex items-center rounded px-3 py-2 font-medium transition ${
                  isActive ? "bg-sky-500/20 text-sky-200" : "hover:bg-slate-900/80 hover:text-slate-200"
                }`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
