import { DocumentTypeFilter } from "@features/workspaces/components/DocumentTypeFilter";
import { WorkspaceSwitcher } from "@features/workspaces/components/WorkspaceSwitcher";
import { UserMenu } from "@features/auth/components/UserMenu";

import "@styles/topbar.css";

interface TopBarProps {
  readonly onMenuToggle: () => void;
}

export function TopBar({ onMenuToggle }: TopBarProps): JSX.Element {
  return (
    <div className="top-bar" role="banner">
      <button
        type="button"
        className="top-bar__menu-button"
        aria-label="Toggle navigation"
        onClick={onMenuToggle}
      >
        <span aria-hidden="true">☰</span>
      </button>
      <div className="top-bar__title">Automatic Data Extractor</div>
      <div className="top-bar__controls">
        <WorkspaceSwitcher />
        <DocumentTypeFilter />
      </div>
      <div className="top-bar__actions">
        <UserMenu />
      </div>
    </div>
  );
}
