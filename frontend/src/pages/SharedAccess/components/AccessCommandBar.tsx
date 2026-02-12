import clsx from "clsx";
import { Search } from "lucide-react";
import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";

interface AccessCommandBarProps {
  readonly searchValue: string;
  readonly onSearchValueChange: (value: string) => void;
  readonly searchPlaceholder?: string;
  readonly searchAriaLabel?: string;
  readonly controls?: ReactNode;
  readonly actions?: ReactNode;
  readonly className?: string;
}

export function AccessCommandBar({
  searchValue,
  onSearchValueChange,
  searchPlaceholder = "Search",
  searchAriaLabel = "Search",
  controls,
  actions,
  className,
}: AccessCommandBarProps) {
  return (
    <div
      className={clsx(
        "rounded-xl border border-border bg-background/80 p-3",
        "flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between",
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative block min-w-0 flex-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            aria-label={searchAriaLabel}
            value={searchValue}
            onChange={(event) => onSearchValueChange(event.target.value)}
            placeholder={searchPlaceholder}
            className="pl-9"
          />
        </div>
        {controls ? <div className="flex flex-wrap items-center gap-2">{controls}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center justify-end gap-2">{actions}</div> : null}
    </div>
  );
}
