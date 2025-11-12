import type { MouseEvent } from "react";

interface TopBarProps {
  readonly currentPath: string | null;
  readonly statusText: string;
  readonly onSelectPath: (path: string) => void;
  readonly onRun: () => void;
  readonly onValidate: () => void;
  readonly onToggleConsole: () => void;
}

export function TopBar({ currentPath, statusText, onSelectPath, onRun, onValidate, onToggleConsole }: TopBarProps) {
  const crumbs = buildCrumbs(currentPath);

  const handleClick = (event: MouseEvent<HTMLButtonElement>, path: string) => {
    event.preventDefault();
    onSelectPath(path);
  };

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200/40 bg-white/90 px-6 py-4 shadow-sm">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Config Package</p>
        <nav className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-700" aria-label="Breadcrumb">
          {crumbs.length === 0 ? <span className="truncate">src/ade_config</span> : null}
          {crumbs.map((crumb, index) => (
            <span key={crumb.path} className="flex items-center gap-2">
              {index > 0 ? <span className="text-slate-400">/</span> : null}
              <button
                type="button"
                onClick={(event) => handleClick(event, crumb.path)}
                className="truncate text-left text-sm font-medium text-brand-700 hover:underline"
              >
                {crumb.label}
              </button>
            </span>
          ))}
        </nav>
        <p className="mt-1 text-xs text-slate-500">{statusText}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <select className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-brand-500 focus:outline-none">
          <option value="active">Active</option>
          <option value="draft">Draft</option>
        </select>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRun}
            className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-brand-400 hover:text-brand-600"
          >
            Run
          </button>
          <button
            type="button"
            onClick={onValidate}
            className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-brand-400 hover:text-brand-600"
          >
            Validate
          </button>
          <button
            type="button"
            onClick={onToggleConsole}
            className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-brand-400 hover:text-brand-600"
          >
            Console
          </button>
        </div>
      </div>
    </header>
  );
}

function buildCrumbs(path: string | null): Array<{ path: string; label: string }> {
  if (!path) {
    return [];
  }
  const segments = path.split("/").filter(Boolean);
  const crumbs: Array<{ path: string; label: string }> = [];
  segments.forEach((segment, index) => {
    const crumbPath = segments.slice(0, index + 1).join("/");
    crumbs.push({ path: crumbPath, label: segment });
  });
  return crumbs;
}
