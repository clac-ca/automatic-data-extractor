import clsx from "clsx";

import { AlertTriangleIcon, ClockIcon } from "@components/icons";

import type { MappingHealth } from "../types";

export function MappingBadge({
  mapping,
  showPending = false,
}: {
  mapping: MappingHealth | null | undefined;
  showPending?: boolean;
}) {
  if (!mapping) {
    return null;
  }
  const isPendingOnly = Boolean(mapping.pending && mapping.attention === 0 && mapping.unmapped === 0);

  // Pending mapping is usually not actionable; keep it quiet unless explicitly requested.
  if (isPendingOnly && !showPending) {
    return null;
  }

  if (isPendingOnly) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
        <ClockIcon className="h-3 w-3" />
        Mapping pending
      </span>
    );
  }

  if (mapping.attention === 0 && mapping.unmapped === 0) {
    return null;
  }

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
      )}
    >
      <AlertTriangleIcon className="h-3 w-3" />
      {mapping.attention > 0 ? `${mapping.attention} need attention` : `${mapping.unmapped} unmapped`}
    </span>
  );
}
