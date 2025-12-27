import clsx from "clsx";

import type { MappingHealth } from "../types";

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.6 2.5 18a1 1 0 0 0 .9 1.5h17.2a1 1 0 0 0 .9-1.5l-7.8-14.4a1 1 0 0 0-1.4 0Z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v6l4 2" />
    </svg>
  );
}

export function MappingBadge({
  mapping,
  showPending = false,
}: {
  mapping: MappingHealth;
  showPending?: boolean;
}) {
  const isPendingOnly = Boolean(mapping.pending && mapping.attention === 0 && mapping.unmapped === 0);

  // Pending mapping is usually not actionable; keep it quiet unless explicitly requested.
  if (isPendingOnly && !showPending) {
    return null;
  }

  if (isPendingOnly) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
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
        "border-amber-200 bg-amber-50 text-amber-700",
      )}
    >
      <AlertIcon className="h-3 w-3" />
      {mapping.attention > 0 ? `${mapping.attention} need attention` : `${mapping.unmapped} unmapped`}
    </span>
  );
}
