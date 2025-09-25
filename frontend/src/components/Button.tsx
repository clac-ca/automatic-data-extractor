import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

import "./Button.css";

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary";
  }
>;

export function Button({ variant = "primary", children, className, ...props }: ButtonProps) {
  const classes = ["ade-button", `ade-button--${variant}`];

  if (className) {
    classes.push(className);
  }

  return (
    <button className={classes.join(" ")} {...props}>
      {children}
    </button>
  );
}
