import clsx from "clsx";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Input } from "@components/ui/input";
import type { WorkspacePerson } from "../types";
import { UNASSIGNED_KEY } from "../filters";
import { CheckIcon, ChevronDownIcon, SearchIcon } from "@components/icons";

export function PeoplePicker({
  people,
  value,
  onChange,
  placeholder,
  multiple = false,
  includeUnassigned = false,
  disabled = false,
  buttonClassName,
  onOpenChange,
}: {
  people: WorkspacePerson[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
  multiple?: boolean;
  includeUnassigned?: boolean;
  disabled?: boolean;
  buttonClassName?: string;
  onOpenChange?: (open: boolean) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);
  const toggleOpen = useCallback(() => {
    setOpen((prev) => {
      if (prev) setQuery("");
      return !prev;
    });
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    onOpenChange?.(open);
  }, [onOpenChange, open]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (containerRef.current?.contains(target)) return;
      close();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    window.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [close, open]);

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
      close();
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
    <div
      ref={containerRef}
      className={clsx("relative", open ? "z-50" : "z-0")}
      data-ignore-row-click="true"
    >
      <button
        type="button"
        disabled={disabled}
        onClick={toggleOpen}
        ref={triggerRef}
        className={clsx(
          "inline-flex min-w-0 items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm transition",
          disabled ? "opacity-60" : "hover:bg-background",
          buttonClassName,
        )}
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-haspopup="listbox"
      >
        <span
          className={clsx(
            "min-w-0 truncate",
            selectedLabels.length === 0 ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {buttonText}
        </span>
        <ChevronDownIcon
          className={clsx("h-3.5 w-3.5 text-muted-foreground transition", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div
          className="absolute left-0 z-50 mt-2 w-72 rounded-2xl border border-border bg-card shadow-lg"
          role="listbox"
          id={listId}
          aria-multiselectable={multiple || undefined}
        >
          <div className="border-b border-border p-2">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search people..."
                className="h-9 pl-9 text-sm"
              />
            </div>
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
                    role="option"
                    aria-selected={selected}
                    className={clsx(
                      "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm transition",
                      selected
                        ? "bg-brand-50 text-foreground dark:bg-brand-500/20 dark:text-brand-200"
                        : "hover:bg-background dark:hover:bg-muted/40",
                    )}
                  >
                    <span className="min-w-0 truncate font-semibold text-foreground">{person.label}</span>
                    {selected ? <CheckIcon className="h-4 w-4 text-brand-600" /> : null}
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
              <button type="button" onClick={close} className="text-xs font-semibold text-brand-600">
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
