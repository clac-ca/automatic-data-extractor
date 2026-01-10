import clsx from "clsx";
import type { ReactNode } from "react";

export function SettingsSection({
  title,
  description,
  actions,
  children,
  tone = "default",
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
  tone?: "default" | "danger";
  className?: string;
}) {
  return (
    <section
      className={clsx(
        "rounded-xl border border-border bg-card p-6",
        tone === "danger" && "border-destructive/40 bg-destructive/5 dark:bg-destructive/10",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      {children ? <div className="mt-4 space-y-4">{children}</div> : null}
    </section>
  );
}
