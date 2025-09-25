import type { PropsWithChildren, ReactNode } from "react";

import "./Page.css";

type PageProps = PropsWithChildren<{
  title: string;
  description?: string;
  actions?: ReactNode;
}>;

export function Page({ title, description, actions, children }: PageProps) {
  return (
    <section className="ade-page">
      <header className="ade-page__header">
        <div>
          <h1>{title}</h1>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="ade-page__actions">{actions}</div> : null}
      </header>
      <div className="ade-page__content">{children}</div>
    </section>
  );
}
