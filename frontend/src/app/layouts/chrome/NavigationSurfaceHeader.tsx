import clsx from "clsx";

export interface NavigationSurfaceHeaderProps {
  readonly label: string;
  readonly collapsed: boolean;
  readonly headingId?: string;
  readonly onToggleCollapse?: () => void;
  readonly collapseLabel?: string;
  readonly expandLabel?: string;
  readonly controlsId?: string;
}

export function NavigationSurfaceHeader({
  label,
  collapsed,
  headingId,
  onToggleCollapse,
  collapseLabel = "Collapse navigation",
  expandLabel = "Expand navigation",
  controlsId,
}: NavigationSurfaceHeaderProps) {
  const ariaLabel = collapsed ? expandLabel : collapseLabel;

  return (
    <div
      className={clsx(
        "flex h-14 items-center border-b border-slate-200 bg-white/80 backdrop-blur-sm",
        collapsed ? "px-2" : "px-3",
      )}
    >
      <div className="flex-1">
        <span
          id={headingId}
          className={clsx(
            "block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 transition-opacity duration-200",
            collapsed ? "sr-only" : "opacity-100",
          )}
        >
          {label}
        </span>
      </div>
      {onToggleCollapse ? (
        <button
          type="button"
          onClick={onToggleCollapse}
          className={clsx(
            "focus-ring inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent text-slate-500 transition-colors duration-200",
            "hover:text-brand-600 focus-visible:text-brand-600",
          )}
          aria-label={ariaLabel}
          aria-expanded={!collapsed}
          aria-controls={controlsId}
          title={ariaLabel}
        >
          <CollapseToggleIcon collapsed={collapsed} />
          <span className="sr-only">{ariaLabel}</span>
        </button>
      ) : null}
    </div>
  );
}

function CollapseToggleIcon({ collapsed }: { readonly collapsed: boolean }) {
  return (
    <svg
      className={clsx(
        "h-4 w-4 text-current transition-transform duration-200 ease-out",
        collapsed ? "rotate-180" : "rotate-0",
      )}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
    >
      <path d="M12 5l-5 5 5 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
