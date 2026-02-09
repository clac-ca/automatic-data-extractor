import clsx from "clsx";
import type { ReactNode } from "react";

interface ResponsiveAdminTableProps<TItem> {
  readonly items: readonly TItem[];
  readonly getItemKey: (item: TItem) => string;
  readonly desktopTable: ReactNode;
  readonly mobileCard: (item: TItem) => ReactNode;
  readonly mobileListLabel: string;
  readonly className?: string;
}

export function ResponsiveAdminTable<TItem>({
  items,
  getItemKey,
  desktopTable,
  mobileCard,
  mobileListLabel,
  className,
}: ResponsiveAdminTableProps<TItem>) {
  return (
    <div className={clsx("space-y-3", className)}>
      <div className="hidden md:block">{desktopTable}</div>
      <div className="space-y-3 md:hidden" aria-label={mobileListLabel}>
        {items.map((item) => (
          <article
            key={getItemKey(item)}
            className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-xs"
          >
            {mobileCard(item)}
          </article>
        ))}
      </div>
    </div>
  );
}
