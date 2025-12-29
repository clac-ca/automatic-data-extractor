import React from "react";
import clsx from "clsx";

export type ActivityBarView = "explorer" | "search" | "scm" | "extensions";

interface ActivityBarProps {
  readonly activeView: ActivityBarView;
  readonly onSelectView: (view: ActivityBarView) => void;
  readonly onOpenSettings: (event: React.MouseEvent<HTMLButtonElement>) => void;
  readonly appearance: "light" | "dark";
}

const ITEMS: Array<{ id: ActivityBarView; label: string; icon: React.ReactNode }> = [
  { id: "explorer", label: "Explorer", icon: <ExplorerIcon /> },
  { id: "search", label: "Search", icon: <SearchIcon /> },
  { id: "scm", label: "Source Control", icon: <SourceControlIcon /> },
  { id: "extensions", label: "Extensions", icon: <ExtensionsIcon /> },
];

export function ActivityBar({ activeView, onSelectView, onOpenSettings, appearance: _appearance }: ActivityBarProps) {
  const theme = {
    bg: "bg-card",
    border: "border-border",
    iconIdle: "text-muted-foreground",
    iconActive: "text-brand-400",
    hover: "hover:text-foreground hover:bg-muted focus-visible:text-foreground",
    indicator: "bg-brand-500",
  };

  return (
    <aside
      className={clsx(
        "flex h-full w-14 flex-col items-center justify-between border-r",
        theme.bg,
        theme.border,
        theme.iconIdle,
      )}
      aria-label="Workbench navigation"
    >
      <div className="flex flex-col items-center gap-1 py-3">
        {ITEMS.map((item) => {
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectView(item.id)}
              className={clsx(
                "relative flex h-10 w-10 items-center justify-center rounded-lg text-base transition",
                active ? theme.iconActive : clsx(theme.iconIdle, theme.hover),
              )}
              aria-label={item.label}
              aria-pressed={active}
            >
              {active ? (
                <span className={clsx("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded", theme.indicator)} />
              ) : null}
              {item.icon}
            </button>
          );
        })}
      </div>
      <div className="flex flex-col items-center gap-3 pb-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className={clsx(
            "flex h-10 w-10 items-center justify-center rounded-lg text-base transition",
            theme.iconIdle,
            theme.hover,
          )}
          aria-label="Open settings"
        >
          <GearIcon />
        </button>
      </div>
    </aside>
  );
}

function ExplorerIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4 8.25h12" stroke="currentColor" strokeWidth="1.2" />
      <path d="M8.25 4v12" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="9" cy="9" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12.7 12.7l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function SourceControlIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6.5 4a1.75 1.75 0 1 1-1.5 0v12m9-8a1.75 1.75 0 1 1-1.5 0v8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M5 9.5h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function ExtensionsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 4.5h4l4 4v6.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.3"
      />
      <path d="M10 4.5v4h4" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M10 6.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M3 10h2m10 0h2M10 3v2m0 10v2M5.2 5.2l1.4 1.4m7 7 1.4 1.4M14.8 5.2l-1.4 1.4m-7 7-1.4 1.4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
