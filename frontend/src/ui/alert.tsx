import clsx from "clsx";
import type { HTMLAttributes, ReactNode } from "react";

type AlertTone = "info" | "success" | "warning" | "danger";

const TONE_STYLE: Record<AlertTone, string> = {
  info: "bg-brand-50 text-brand-700 ring-brand-100",
  success: "bg-success-50 text-success-700 ring-success-100",
  warning: "bg-warning-50 text-warning-700 ring-warning-100",
  danger: "bg-danger-50 text-danger-700 ring-danger-100",
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
