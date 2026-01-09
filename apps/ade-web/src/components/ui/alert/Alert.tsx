import clsx from "clsx";
import type { HTMLAttributes, ReactNode } from "react";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONE_STYLE: Record<AlertTone, string> = {
  info: "bg-sky-50 text-sky-700 ring-sky-100 dark:bg-sky-500/10 dark:text-sky-200 dark:ring-sky-500/20",
  success:
    "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-200 dark:ring-emerald-500/20",
  warning:
    "bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-200 dark:ring-amber-500/20",
  danger: "bg-destructive/10 text-destructive ring-destructive/20 dark:bg-destructive/20",
};

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  readonly tone?: AlertTone;
  readonly heading?: ReactNode;
  readonly icon?: ReactNode;
}

export function Alert({ tone = "info", heading, icon, className, children, ...props }: AlertProps) {
  return (
    <div
      role="status"
      className={clsx(
        "flex w-full items-start gap-3 rounded-lg px-4 py-3 text-sm ring-1 ring-inset",
        TONE_STYLE[tone],
        className,
      )}
      {...props}
    >
      {icon ? <span aria-hidden="true">{icon}</span> : null}
      <div className="space-y-1">
        {heading ? <p className="font-semibold">{heading}</p> : null}
        {children ? <p className="leading-relaxed">{children}</p> : null}
      </div>
    </div>
  );
}
