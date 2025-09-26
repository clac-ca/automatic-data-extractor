import type { MouseEvent } from "react";
import { NavLink } from "react-router-dom";

import "@styles/sidenav.css";

interface NavigationItem {
  readonly key: string;
  readonly label: string;
  readonly to: string | null;
  readonly disabled?: boolean;
}

interface SideNavigationProps {
  readonly workspaceId: string | null;
  readonly onNavigate?: () => void;
}

export function SideNavigation({ workspaceId, onNavigate }: SideNavigationProps): JSX.Element {
  const items: NavigationItem[] = buildNavigation(workspaceId);

  const handleClick = (event: MouseEvent<HTMLAnchorElement>, item: NavigationItem) => {
    if (item.disabled) {
      event.preventDefault();
      return;
    }

    onNavigate?.();
  };

  return (
    <nav aria-label="Primary" className="side-nav">
      <ul className="side-nav__list">
        {items.map((item) => (
          <li key={item.key}>
            {item.to ? (
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  `side-nav__link ${item.disabled ? "side-nav__link--disabled" : ""} ${
                    isActive ? "side-nav__link--active" : ""
                  }`
                }
                onClick={(event) => handleClick(event, item)}
              >
                {item.label}
              </NavLink>
            ) : (
              <span className="side-nav__link side-nav__link--disabled">{item.label}</span>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}

function buildNavigation(workspaceId: string | null): NavigationItem[] {
  const workspacePath = workspaceId ? `/workspaces/${workspaceId}` : null;

  return [
    {
      key: "workspaces",
      label: "Workspaces",
      to: "/workspaces"
    },
    {
      key: "overview",
      label: "Overview",
      to: workspacePath ? `${workspacePath}/overview` : null,
      disabled: !workspacePath
    },
    {
      key: "documents",
      label: "Documents",
      to: workspacePath ? `${workspacePath}/documents` : null,
      disabled: !workspacePath
    },
    {
      key: "jobs",
      label: "Jobs",
      to: workspacePath ? `${workspacePath}/jobs` : null,
      disabled: !workspacePath
    },
    {
      key: "results",
      label: "Results",
      to: workspacePath ? `${workspacePath}/results` : null,
      disabled: !workspacePath
    },
    {
      key: "configurations",
      label: "Configurations",
      to: workspacePath ? `${workspacePath}/configurations` : null,
      disabled: !workspacePath
    },
    {
      key: "settings",
      label: "Workspace settings",
      to: workspacePath ? `${workspacePath}/settings` : null,
      disabled: !workspacePath
    }
  ];
}
