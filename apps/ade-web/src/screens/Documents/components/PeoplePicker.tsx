import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";

import type { WorkspacePerson } from "../types";

const UNASSIGNED_KEY = "__unassigned__";

export function PeoplePicker({
  people,
  value,
  onChange,
  placeholder,
  multiple = false,
  includeUnassigned = false,
  disabled = false,
  buttonClassName,
}: {
  people: WorkspacePerson[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
  multiple?: boolean;
  includeUnassigned?: boolean;
  disabled?: boolean;
  buttonClassName?: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (!open) return;
      const target = event.target as Node | null;
      if (containerRef.current && target && !containerRef.current.contains(target)) {
        setOpen(false);
        setQuery("");
      }
    }
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const allOptions = useMemo(() => {
    const base = people.slice().sort((a, b) => a.label.localeCompare(b.label));
    if (!includeUnassigned) return base;
    return [{ key: UNASSIGNED_KEY, label: "Unassigned", kind: "label" as const }, ...base];
  }, [includeUnassigned, people]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allOptions;
    return allOptions.filter((p) => p.label.toLowerCase().includes(q));
  }, [allOptions, query]);

  const selectedLabels = useMemo(() => {
    const map = new Map(allOptions.map((p) => [p.key, p.label]));
    const labels = value.map((k) => map.get(k) ?? (k === UNASSIGNED_KEY ? "Unassigned" : k));
    return labels.filter(Boolean);
  }, [allOptions, value]);

  function toggle(key: string) {
    if (disabled) return;

    if (!multiple) {
      onChange([key]);
      setOpen(false);
      setQuery("");
      return;
    }
    const next = new Set(value);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(Array.from(next));
  }

  const buttonText =
    selectedLabels.length === 0
      ? placeholder
      : multiple
        ? selectedLabels.length === 1
          ? selectedLabels[0]
          : `${selectedLabels[0]} +${selectedLabels.length - 1}`
        : selectedLabels[0];

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={clsx(
          "inline-flex min-w-0 items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm transition",
          disabled ? "opacity-60" : "hover:border-brand-300",
          buttonClassName,
        )}
      >
        <span
          className={clsx(
            "min-w-0 truncate",
            selectedLabels.length === 0 ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {buttonText}
        </span>
        <span className="text-muted-foreground" aria-hidden>
          v
        </span>
      </button>

      {open ? (
        <div className="absolute left-0 z-30 mt-2 w-72 rounded-2xl border border-border bg-card shadow-lg">
          <div className="border-b border-border p-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search people..."
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand-300"
            />
          </div>
          <div className="max-h-72 overflow-auto p-2">
            {filtered.length === 0 ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">No matches.</div>
            ) : (
              filtered.map((person) => {
                const selected = value.includes(person.key);
                return (
                  <button
                    key={person.key}
                    type="button"
                    onClick={() => toggle(person.key)}
                    className={clsx(
                      "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm transition",
                      selected ? "bg-brand-50 dark:bg-brand-500/20" : "hover:bg-background dark:hover:bg-muted/40",
                    )}
                  >
                    <span className="min-w-0 truncate font-semibold text-foreground">{person.label}</span>
                    {multiple ? (
                      <span
                        className={clsx(
                          "text-xs font-semibold",
                          selected ? "text-brand-700 dark:text-brand-200" : "text-muted-foreground",
                        )}
                      >
                        {selected ? "Selected" : "Select"}
                      </span>
                    ) : null}
                  </button>
                );
              })
            )}
          </div>

          {multiple && value.length > 0 ? (
            <div className="flex items-center justify-between border-t border-border px-3 py-2">
              <button
                type="button"
                onClick={() => onChange([])}
                className="text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setQuery("");
                }}
                className="text-xs font-semibold text-brand-600"
              >
                Done
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function normalizeSingleAssignee(keys: string[]) {
  if (keys.length === 0) return null;
  if (keys[0] === UNASSIGNED_KEY) return null;
  return keys[0];
}

export function unassignedKey() {
  return UNASSIGNED_KEY;
}
