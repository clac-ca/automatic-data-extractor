import type { ReactNode } from "react";

import "@styles/card.css";

interface CardProps {
  readonly title?: string;
  readonly subtitle?: string;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
}

export function Card({ title, subtitle, children, footer }: CardProps): JSX.Element {
  return (
    <section className="card">
      {title ? (
        <header className="card__header">
          <h2 className="card__title">{title}</h2>
          {subtitle ? <p className="card__subtitle">{subtitle}</p> : null}
        </header>
      ) : null}
      <div className="card__content">{children}</div>
      {footer ? <footer className="card__footer">{footer}</footer> : null}
    </section>
  );
}
