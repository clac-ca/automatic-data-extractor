import type { ButtonHTMLAttributes, ReactNode } from "react";

import "@styles/button.css";

type ButtonVariant = "primary" | "secondary" | "ghost";

type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly icon?: ReactNode;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  icon,
  className = "",
  ...rest
}: ButtonProps): JSX.Element {
  const classes = ["btn", `btn--${variant}`, `btn--${size}`, className].join(" ").trim();

  return (
    <button className={classes} {...rest}>
      {icon ? <span className="btn__icon">{icon}</span> : null}
      <span>{children}</span>
    </button>
  );
}
