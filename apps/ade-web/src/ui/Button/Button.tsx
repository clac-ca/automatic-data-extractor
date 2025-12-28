import clsx from "clsx";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly isLoading?: boolean;
}

const VARIANT_STYLE: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-on-brand hover:bg-brand-700 focus-visible:ring-brand-500 disabled:bg-brand-300",
  secondary:
    "bg-card text-muted-foreground border border-border hover:bg-muted focus-visible:ring-ring disabled:text-muted-foreground",
  ghost: "bg-transparent text-muted-foreground hover:bg-muted focus-visible:ring-ring",
  danger:
    "bg-danger-600 text-on-danger hover:bg-danger-700 focus-visible:ring-danger-500 disabled:bg-danger-300",
};

const SIZE_STYLE: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      type = "button",
      variant = "primary",
      size = "md",
      isLoading = false,
      className,
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={isLoading || undefined}
        className={clsx(
          "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed",
          VARIANT_STYLE[variant],
          SIZE_STYLE[size],
          className,
        )}
        {...props}
      >
        {isLoading ? (
          <span
            aria-hidden="true"
            className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          />
        ) : null}
        <span>{children}</span>
      </button>
    );
  },
);

Button.displayName = "Button";
