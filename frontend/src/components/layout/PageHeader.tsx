import type { ReactNode } from "react";

import "@styles/page-header.css";

interface PageHeaderProps {
  readonly title: string;
  readonly description?: string;
  readonly actions?: ReactNode;
  readonly breadcrumb?: ReactNode;
}

export function PageHeader({ title, description, actions, breadcrumb }: PageHeaderProps): JSX.Element {
  return (
    <header className="page-header">
      <div>
        {breadcrumb ? <div className="page-header__breadcrumb">{breadcrumb}</div> : null}
        <h1 className="page-header__title">{title}</h1>
        {description ? <p className="page-header__description">{description}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}
