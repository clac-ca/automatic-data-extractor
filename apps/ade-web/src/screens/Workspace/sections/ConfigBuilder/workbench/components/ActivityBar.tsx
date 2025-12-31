import React from "react";
import clsx from "clsx";

import { ExtensionsIcon, ExplorerIcon, GearIcon, SearchIcon, SourceControlIcon } from "@ui/Icons";

export type ActivityBarView = "explorer" | "search" | "scm" | "extensions";

interface ActivityBarProps {
  readonly activeView: ActivityBarView;
  readonly onSelectView: (view: ActivityBarView) => void;
  readonly onOpenSettings: (event: React.MouseEvent<HTMLButtonElement>) => void;
  readonly appearance: "light" | "dark";
}

const ITEMS: Array<{ id: ActivityBarView; label: string; icon: React.ReactNode }> = [
  { id: "explorer", label: "Explorer", icon: <ExplorerIcon className="h-5 w-5" /> },
  { id: "search", label: "Search", icon: <SearchIcon className="h-5 w-5" /> },
  { id: "scm", label: "Source Control", icon: <SourceControlIcon className="h-5 w-5" /> },
  { id: "extensions", label: "Extensions", icon: <ExtensionsIcon className="h-5 w-5" /> },
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
          <GearIcon className="h-5 w-5" />
        </button>
      </div>
    </aside>
  );
}
