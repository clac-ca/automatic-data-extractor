import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function SettingsCommandBar({
  searchValue,
  onSearchValueChange,
  searchPlaceholder,
  controls,
  secondaryActions,
  primaryAction,
  className,
}: {
  readonly searchValue: string;
  readonly onSearchValueChange: (value: string) => void;
  readonly searchPlaceholder: string;
  readonly controls?: ReactNode;
  readonly secondaryActions?: ReactNode;
  readonly primaryAction?: ReactNode;
  readonly className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-3", className)}>
      <div className="min-w-[220px] flex-1">
        <Input
          value={searchValue}
          onChange={(event) => onSearchValueChange(event.target.value)}
          placeholder={searchPlaceholder}
          aria-label={searchPlaceholder}
        />
      </div>
      {controls ? <div className="flex flex-wrap items-center gap-2">{controls}</div> : null}
      {secondaryActions ? (
        <div className="flex flex-wrap items-center gap-2">{secondaryActions}</div>
      ) : null}
      {primaryAction ? <div className="ml-auto flex items-center gap-2">{primaryAction}</div> : null}
    </div>
  );
}
