import clsx from "clsx";
import type { ReactNode } from "react";

type PageStateVariant = "loading" | "empty" | "error";

interface PageStateProps {
  readonly title: string;
  readonly description?: ReactNode;
  readonly action?: ReactNode;
  readonly variant?: PageStateVariant;
  readonly className?: string;
}

const VARIANT_ICON: Record<PageStateVariant, string> = {
  loading: "animate-spin border-2 border-brand-500 border-t-transparent",
  empty: "bg-border",
  error: "bg-danger-500",
};

export function PageState({
  title,
  description,
  action,
  variant = "empty",
  className,
}: PageStateProps) {
  return (
    <div
      className={clsx(
        "flex min-h-[240px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/70 px-6 py-12 text-center text-sm text-muted-foreground",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={clsx("mb-4 h-8 w-8 rounded-full border-current", VARIANT_ICON[variant])}
      />
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {description ? <p className="mt-2 max-w-md leading-relaxed">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
