import type { ReactNode } from "react";

import "@styles/empty-state.css";

interface EmptyStateProps {
  readonly icon?: ReactNode;
  readonly title: string;
  readonly description?: string;
  readonly action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps): JSX.Element {
  return (
    <div className="empty-state">
      {icon ? <div className="empty-state__icon">{icon}</div> : null}
      <h2 className="empty-state__title">{title}</h2>
      {description ? <p className="empty-state__description">{description}</p> : null}
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}
