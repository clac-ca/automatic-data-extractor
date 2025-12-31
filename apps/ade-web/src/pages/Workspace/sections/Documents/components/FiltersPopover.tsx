import clsx from "clsx";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ChevronDownSmallIcon, FilterIcon } from "@components/icons";

import type { DocumentsFilters, DocumentStatus, FileType, TagMode, WorkspacePerson } from "../types";
import { fileTypeLabel } from "../utils";
import { PeoplePicker } from "./PeoplePicker";
import { TagPicker } from "./TagPicker";

const STATUS_OPTIONS: { value: DocumentStatus; label: string }[] = [
  { value: "queued", label: "Queued" },
  { value: "processing", label: "Processing" },
  { value: "ready", label: "Processed" },
  { value: "failed", label: "Failed" },
  { value: "archived", label: "Archived" },
];

const FILETYPE_OPTIONS: { value: FileType; label: string }[] = [
  { value: "xlsx", label: "XLSX" },
  { value: "xls", label: "XLS" },
  { value: "csv", label: "CSV" },
  { value: "pdf", label: "PDF" },
];

export function FiltersPopover({
  workspaceId,
  filters,
  onChange,
  people,
}: {
  workspaceId: string;
  filters: DocumentsFilters;
  onChange: (next: DocumentsFilters) => void;
  people: WorkspacePerson[];
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

  const activeCount =
    filters.statuses.length + filters.fileTypes.length + filters.tags.length + filters.assignees.length;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-8 items-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground shadow-sm hover:border-brand-300"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <FilterIcon className="h-4 w-4" />
        Filters
        {activeCount > 0 ? (
          <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
            {activeCount}
          </span>
        ) : null}
        <ChevronDownSmallIcon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
      </button>

      {open ? (
        <div className="absolute left-0 z-30 mt-2 w-[22rem] rounded-2xl border border-border bg-card p-4 shadow-lg">
          <div className="flex flex-col gap-4">
            <FilterGroup label="Status">
              <FilterPills
                options={STATUS_OPTIONS}
                value={filters.statuses}
                onToggle={(status) => {
                  const next = new Set(filters.statuses);
                  if (next.has(status)) next.delete(status);
                  else next.add(status);
                  onChange({ ...filters, statuses: Array.from(next) });
                }}
              />
            </FilterGroup>

            <FilterGroup label="File type">
              <FilterPills
                options={FILETYPE_OPTIONS}
                value={filters.fileTypes}
                onToggle={(ft) => {
                  const next = new Set(filters.fileTypes);
                  if (next.has(ft)) next.delete(ft);
                  else next.add(ft);
                  onChange({ ...filters, fileTypes: Array.from(next) });
                }}
                renderLabel={(ft) => fileTypeLabel(ft)}
              />
            </FilterGroup>

            <FilterGroup label="Tags">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1 rounded-full border border-border bg-background px-2 py-1">
                  {(["any", "all"] as TagMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={clsx(
                        "rounded-full px-2 py-0.5 text-[11px] font-semibold transition",
                        filters.tagMode === mode
                          ? "bg-card text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                      onClick={() => onChange({ ...filters, tagMode: mode })}
                    >
                      {mode === "any" ? "Any" : "All"}
                    </button>
                  ))}
                </div>

                <TagPicker
                  workspaceId={workspaceId}
                  selected={filters.tags}
                  onToggle={(tag) => {
                    const next = filters.tags.includes(tag)
                      ? filters.tags.filter((t) => t !== tag)
                      : [...filters.tags, tag];
                    onChange({ ...filters, tags: next });
                  }}
                  placeholder={filters.tags.length ? "Edit tags" : "Filter tags"}
                />
              </div>
            </FilterGroup>

            <FilterGroup label="Assignee">
              <PeoplePicker
                people={people}
                value={filters.assignees}
                onChange={(assignees) => onChange({ ...filters, assignees })}
                placeholder="Assignee..."
                multiple
                includeUnassigned
              />
            </FilterGroup>

            <div className="flex items-center justify-between border-t border-border pt-3">
              <button
                type="button"
                onClick={() =>
                  onChange({
                    statuses: [],
                    fileTypes: [],
                    tags: [],
                    tagMode: "any",
                    assignees: [],
                  })
                }
                className="text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                Clear filters
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

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold text-muted-foreground">{label}</div>
      {children}
    </div>
  );
}

function FilterPills<T extends string>({
  options,
  value,
  onToggle,
  renderLabel,
}: {
  options: { value: T; label: string }[];
  value: T[];
  onToggle: (value: T) => void;
  renderLabel?: (value: T) => string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      {options.map((option) => {
        const active = value.includes(option.value);
        const text = renderLabel ? renderLabel(option.value) : option.label;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onToggle(option.value)}
            className={clsx(
              "rounded-full border px-2 py-0.5 text-[11px] font-semibold transition",
              active
                ? "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-500/40 dark:bg-brand-500/20 dark:text-brand-200"
                : "border-transparent text-muted-foreground hover:bg-background dark:hover:bg-muted/40 hover:text-foreground",
            )}
          >
            {text}
          </button>
        );
      })}
    </div>
  );
}
