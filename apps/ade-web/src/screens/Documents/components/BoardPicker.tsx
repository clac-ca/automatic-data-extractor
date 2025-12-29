import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";

import type { BoardOption } from "../types";
import { DEFAULT_BOARD_ID, DEFAULT_BOARD_LABEL, formatBoardLabel, normalizeBoardId } from "../utils";

export function BoardPicker({
  boards,
  value,
  onChange,
  placeholder,
  disabled = false,
  buttonClassName,
}: {
  boards: BoardOption[];
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
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

  const normalizedValue = useMemo(() => {
    const normalized = normalizeBoardId(value.replace(/^board:/, ""));
    return normalized || DEFAULT_BOARD_ID;
  }, [value]);

  const options = useMemo(() => {
    const unique = new Map<string, BoardOption>();
    boards.forEach((board) => {
      unique.set(board.id, board);
    });
    if (!unique.has(DEFAULT_BOARD_ID)) {
      unique.set(DEFAULT_BOARD_ID, { id: DEFAULT_BOARD_ID, label: DEFAULT_BOARD_LABEL, isDefault: true });
    }
    return Array.from(unique.values());
  }, [boards]);

  const selectedLabel = useMemo(() => {
    const match = options.find((option) => option.id === normalizedValue);
    return match?.label ?? formatBoardLabel(normalizedValue);
  }, [normalizedValue, options]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((option) => option.label.toLowerCase().includes(q) || option.id.toLowerCase().includes(q));
  }, [options, query]);

  const createCandidate = useMemo(() => {
    const normalized = normalizeBoardId(query.replace(/^board:/, ""));
    if (!normalized) return null;
    const exists = options.some((option) => option.id === normalized);
    return exists ? null : normalized;
  }, [options, query]);

  const buttonText = selectedLabel || placeholder;

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
            selectedLabel ? "text-foreground" : "text-muted-foreground",
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
              placeholder="Search or create board..."
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand-300"
              autoFocus
            />
          </div>
          <div className="max-h-72 overflow-auto p-2">
            {createCandidate ? (
              <button
                type="button"
                onClick={() => {
                  onChange(createCandidate);
                  setOpen(false);
                  setQuery("");
                }}
                className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm transition hover:bg-background"
              >
                <span className="min-w-0 truncate font-semibold text-foreground">Create “{createCandidate}”</span>
                <span className="text-xs font-semibold text-muted-foreground">new</span>
              </button>
            ) : null}

            {filtered.length === 0 ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">No boards yet.</div>
            ) : (
              filtered.map((board) => {
                const selected = board.id === normalizedValue;
                return (
                  <button
                    key={board.id}
                    type="button"
                    onClick={() => {
                      onChange(board.id);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={clsx(
                      "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm transition",
                      selected ? "bg-brand-50 dark:bg-brand-500/20" : "hover:bg-background dark:hover:bg-muted/40",
                    )}
                  >
                    <span className="min-w-0 truncate font-semibold text-foreground">{board.label}</span>
                    {board.isDefault ? (
                      <span className="text-xs font-semibold text-muted-foreground">Default</span>
                    ) : null}
                  </button>
                );
              })
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
