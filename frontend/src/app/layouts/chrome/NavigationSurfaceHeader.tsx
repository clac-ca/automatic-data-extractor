import clsx from "clsx";

export interface NavigationSurfaceHeaderProps {
  readonly label: string;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly collapseLabel: string;
  readonly expandLabel: string;
}

export function NavigationSurfaceHeader({
  label,
  collapsed,
  onToggleCollapse,
  collapseLabel,
  expandLabel,
}: NavigationSurfaceHeaderProps) {
  return (
    <div className="flex h-16 items-center gap-2 border-b border-slate-200 px-3">
      <span
        className={clsx(
          "text-xs font-semibold uppercase tracking-wide text-slate-500 transition-[opacity,transform] duration-200",
          collapsed ? "pointer-events-none opacity-0 -translate-x-2" : "opacity-100 translate-x-0",
        )}
        aria-hidden={collapsed}
      >
        {label}
      </span>
      <button
        type="button"
        onClick={onToggleCollapse}
        className="focus-ring ml-auto inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label={collapsed ? expandLabel : collapseLabel}
        aria-pressed={collapsed}
      >
        <CollapseToggleIcon collapsed={collapsed} />
      </button>
    </div>
  );
}

function CollapseToggleIcon({ collapsed }: { readonly collapsed: boolean }) {
  return collapsed ? (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 4h12v12H4z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9 10l-2 2m2-2l-2-2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 4h12v12H4z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11 10l2-2m-2 2l2 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
