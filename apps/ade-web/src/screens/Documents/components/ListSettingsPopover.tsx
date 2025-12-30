import clsx from "clsx";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Select } from "@ui/Select";

import {
  DEFAULT_LIST_SETTINGS,
  LIST_DENSITIES,
  LIST_PAGE_SIZES,
  LIST_REFRESH_INTERVALS,
} from "../listSettings";
import type { ListPageSize, ListRefreshInterval, ListSettings } from "../types";
import { ChevronDownIcon, SettingsIcon } from "./icons";

export function ListSettingsPopover({
  settings,
  onChange,
}: {
  settings: ListSettings;
  onChange: (next: ListSettings) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (!open) return;
      const target = event.target as Node | null;
      if (containerRef.current && target && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const isDefault = useMemo(
    () =>
      settings.pageSize === DEFAULT_LIST_SETTINGS.pageSize &&
      settings.refreshInterval === DEFAULT_LIST_SETTINGS.refreshInterval &&
      settings.density === DEFAULT_LIST_SETTINGS.density,
    [settings],
  );

  const update = (patch: Partial<ListSettings>) => onChange({ ...settings, ...patch });

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={clsx(
          "inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold shadow-sm transition",
          open ? "text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <SettingsIcon className="h-4 w-4" />
        List settings
        <ChevronDownIcon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
      </button>

      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-[20.5rem] rounded-2xl border border-border bg-card p-4 shadow-lg">
          <div className="flex flex-col gap-4">
            <SettingsRow label="Records per page">
              <Select
                aria-label="Records per page"
                value={String(settings.pageSize)}
                onChange={(event) => update({ pageSize: Number(event.target.value) as ListPageSize })}
              >
                {LIST_PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </Select>
            </SettingsRow>

            <SettingsRow label="Refresh frequency">
              <Select
                aria-label="Refresh frequency"
                value={settings.refreshInterval}
                onChange={(event) => update({ refreshInterval: event.target.value as ListRefreshInterval })}
              >
                {LIST_REFRESH_INTERVALS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </SettingsRow>

            <SettingsRow label="Display density">
              <div
                className="flex items-center gap-1 rounded-full border border-border bg-background p-1"
                role="radiogroup"
                aria-label="Display density"
              >
                {LIST_DENSITIES.map((density) => {
                  const isSelected = settings.density === density.value;
                  return (
                    <button
                      key={density.value}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      onClick={() => update({ density: density.value })}
                      className={clsx(
                        "rounded-full px-3 py-1 text-[11px] font-semibold transition",
                        isSelected
                          ? "bg-card text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {density.label}
                    </button>
                  );
                })}
              </div>
            </SettingsRow>

            <div className="flex items-center justify-between border-t border-border pt-3">
              <button
                type="button"
                onClick={() => update(DEFAULT_LIST_SETTINGS)}
                className={clsx(
                  "text-xs font-semibold",
                  isDefault ? "text-muted-foreground/60" : "text-muted-foreground hover:text-foreground",
                )}
                disabled={isDefault}
              >
                Reset defaults
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-xs font-semibold text-brand-600"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SettingsRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="text-xs font-semibold text-muted-foreground">{label}</div>
      <div className="w-40">{children}</div>
    </div>
  );
}
