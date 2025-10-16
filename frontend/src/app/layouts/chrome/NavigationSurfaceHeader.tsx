import clsx from "clsx";

export interface NavigationSurfaceHeaderProps {
  readonly label: string;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly collapseLabel: string;
  readonly expandLabel: string;
  readonly controlsId?: string;
  readonly headingId?: string;
}

export function NavigationSurfaceHeader({
  label,
  collapsed,
  onToggleCollapse,
  collapseLabel,
  expandLabel,
  controlsId,
  headingId,
}: NavigationSurfaceHeaderProps) {
  return (
    <div className="flex h-16 items-center gap-2 border-b border-slate-200 bg-white/60 px-2">
      <span
        id={headingId}
        className={clsx(
          "flex-1 overflow-hidden text-xs font-semibold uppercase tracking-wide text-slate-500 transition-[opacity,transform,width] duration-200",
          collapsed
            ? "pointer-events-none -translate-x-2 opacity-0 basis-0"
            : "basis-auto translate-x-0 opacity-100",
        )}
        aria-hidden={collapsed}
      >
        {label}
      </span>
      <button
        type="button"
        onClick={onToggleCollapse}
        className={clsx(
          "focus-ring relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition-colors duration-200",
          collapsed ? "bg-white" : "bg-slate-50",
          "hover:border-brand-200 hover:text-brand-700",
        )}
        aria-label={collapsed ? expandLabel : collapseLabel}
        aria-expanded={!collapsed}
        aria-controls={controlsId}
      >
        <CollapseToggleIcon collapsed={collapsed} />
      </button>
    </div>
  );
}

function CollapseToggleIcon({ collapsed }: { readonly collapsed: boolean }) {
  return collapsed ? (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M7 5l6 5-6 5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 5l6 5-6 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M13 5l-6 5 6 5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16 5l-6 5 6 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
