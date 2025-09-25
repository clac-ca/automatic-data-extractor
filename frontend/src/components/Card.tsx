import type { HTMLAttributes, PropsWithChildren } from "react";

import "./Card.css";

type CardProps = PropsWithChildren<HTMLAttributes<HTMLDivElement>>;

export function Card({ className, children, ...props }: CardProps) {
  const classes = ["ade-card"];

  if (className) {
    classes.push(className);
  }

  return (
    <div className={classes.join(" ")} {...props}>
      {children}
    </div>
  );
}
