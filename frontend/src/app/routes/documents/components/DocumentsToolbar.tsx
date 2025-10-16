import clsx from "clsx";
import { useId, useMemo, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { Button, Input, Select } from "../../../../ui";
import type { UploaderFilterValue } from "../utils";
import { formatStatusLabel } from "../utils";

const STATUS_OPTIONS: readonly { value: string; label: string }[] = [
  { value: "uploaded", label: formatStatusLabel("uploaded") },
  { value: "processing", label: formatStatusLabel("processing") },
  { value: "processed", label: formatStatusLabel("processed") },
  { value: "failed", label: formatStatusLabel("failed") },
  { value: "archived", label: formatStatusLabel("archived") },
];

interface DocumentsToolbarProps {
  readonly uploader: UploaderFilterValue;
  readonly onUploaderChange: (value: UploaderFilterValue) => void;
  readonly statuses: readonly string[];
  readonly onStatusesChange: (values: string[]) => void;
  readonly tags: readonly string[];
  readonly onAddTag: (tag: string) => void;
  readonly onRemoveTag: (tag: string) => void;
  readonly availableTags: readonly string[];
  readonly createdFrom?: string;
  readonly createdTo?: string;
  readonly onCreatedRangeChange: (from?: string, to?: string) => void;
  readonly lastRunFrom?: string;
  readonly lastRunTo?: string;
  readonly onLastRunRangeChange: (from?: string, to?: string) => void;
  readonly search: string;
  readonly onSearchChange: (value: string) => void;
  readonly onClearFilters: () => void;
  readonly onUploadClick: () => void;
  readonly isUploading: boolean;
  readonly itemCount: number;
  readonly page: number;
  readonly perPage: number;
  readonly onPerPageChange: (value: number) => void;
  readonly canClearFilters: boolean;
}

export function DocumentsToolbar({
  uploader,
  onUploaderChange,
  statuses,
  onStatusesChange,
  tags,
  onAddTag,
  onRemoveTag,
  availableTags,
  createdFrom,
  createdTo,
  onCreatedRangeChange,
  lastRunFrom,
  lastRunTo,
  onLastRunRangeChange,
  search,
  onSearchChange,
  onClearFilters,
  onUploadClick,
  isUploading,
  itemCount,
  page,
  perPage,
  onPerPageChange,
  canClearFilters,
}: DocumentsToolbarProps) {
  const statusSelectId = useId();
  const tagInputId = useId();
  const createdFromId = useId();
  const createdToId = useId();
  const lastRunFromId = useId();
  const lastRunToId = useId();

  const [tagDraft, setTagDraft] = useState("");

  const perPageOptions = useMemo(
    () => [25, 50, 100, 200],
    [],
  );

  const handleStatusChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const values = Array.from(event.target.selectedOptions).map((option) => option.value);
    onStatusesChange(values);
  };

  const handleTagKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      const value = tagDraft.trim();
      if (value.length > 0) {
        onAddTag(value);
        setTagDraft("");
      }
    }
  };

  const handleTagBlur = () => {
    const value = tagDraft.trim();
    if (value.length > 0) {
      onAddTag(value);
      setTagDraft("");
    }
  };

  const summary = `${itemCount === 1 ? "1 result" : `${itemCount} results`} • Page ${page}`;

  return (
    <div className="sticky top-0 z-20 flex flex-col gap-3 border-b border-slate-200 bg-white px-5 py-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <UploaderToggle value={uploader} onChange={onUploaderChange} />
          <div className="flex flex-col gap-1">
            <label htmlFor={statusSelectId} className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Status
            </label>
            <Select
              id={statusSelectId}
              multiple
              value={statuses}
              onChange={handleStatusChange}
              className="h-[4.5rem] w-48"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <TagFilter
            id={tagInputId}
            value={tagDraft}
            tags={tags}
            onChange={setTagDraft}
            onKeyDown={handleTagKeyDown}
            onBlur={handleTagBlur}
            onRemove={onRemoveTag}
            availableTags={availableTags}
          />
        </div>
        <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <span aria-live="polite">{summary}</span>
          <Select
            value={perPage}
            onChange={(event) => onPerPageChange(Number.parseInt(event.target.value, 10))}
            className="h-9 w-24"
          >
            {perPageOptions.map((option) => (
              <option key={option} value={option}>
                {option} / page
              </option>
            ))}
          </Select>
          <Button onClick={onUploadClick} isLoading={isUploading} size="sm">
            Upload
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <DateRange
          idFrom={createdFromId}
          idTo={createdToId}
          label="Created"
          from={createdFrom}
          to={createdTo}
          onChange={onCreatedRangeChange}
        />
        <DateRange
          idFrom={lastRunFromId}
          idTo={lastRunToId}
          label="Last run"
          from={lastRunFrom}
          to={lastRunTo}
          onChange={onLastRunRangeChange}
        />
        <SearchField value={search} onChange={onSearchChange} />
        <Button variant="secondary" onClick={onClearFilters} disabled={!canClearFilters}>
          Clear all
        </Button>
      </div>
    </div>
  );
}

function UploaderToggle({ value, onChange }: { readonly value: UploaderFilterValue; readonly onChange: (value: UploaderFilterValue) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Showing</span>
      <div className="flex overflow-hidden rounded-md border border-slate-200">
        <button
          type="button"
          onClick={() => onChange("all")}
          className={clsxToggle(value === "all")}
        >
          All
        </button>
        <button
          type="button"
          onClick={() => onChange("me")}
          className={clsxToggle(value === "me")}
        >
          Me
        </button>
      </div>
    </div>
  );
}

function clsxToggle(active: boolean) {
  return clsx(
    "px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition",
    active ? "bg-brand-600 text-white" : "bg-white text-slate-600 hover:bg-slate-100",
  );
}

interface TagFilterProps {
  readonly id: string;
  readonly value: string;
  readonly tags: readonly string[];
  readonly availableTags: readonly string[];
  readonly onChange: (value: string) => void;
  readonly onKeyDown: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  readonly onBlur: () => void;
  readonly onRemove: (tag: string) => void;
}

function TagFilter({ id, value, tags, availableTags, onChange, onKeyDown, onBlur, onRemove }: TagFilterProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Tags
      </label>
      <div className="flex min-w-[14rem] flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 px-2 py-1">
          {tags.length === 0 ? (
            <span className="text-xs text-slate-400">Any tag</span>
          ) : (
            tags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => onRemove(tag)}
                className="flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200"
              >
                {tag}
                <span aria-hidden="true">×</span>
                <span className="sr-only">Remove tag {tag}</span>
              </button>
            ))
          )}
        </div>
        <Input
          id={id}
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          onBlur={onBlur}
          list={`${id}-options`}
          placeholder="Add tag"
          className="h-9"
        />
        <datalist id={`${id}-options`}>
          {availableTags.map((tag) => (
            <option key={tag} value={tag} />
          ))}
        </datalist>
      </div>
    </div>
  );
}

interface DateRangeProps {
  readonly idFrom: string;
  readonly idTo: string;
  readonly label: string;
  readonly from?: string;
  readonly to?: string;
  readonly onChange: (from?: string, to?: string) => void;
}

function DateRange({ idFrom, idTo, label, from, to, onChange }: DateRangeProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="flex items-center gap-2">
        <Input
          id={idFrom}
          type="date"
          value={from ?? ""}
          onChange={(event) => onChange(event.target.value || undefined, to)}
          className="h-9"
        />
        <span className="text-slate-400">to</span>
        <Input
          id={idTo}
          type="date"
          value={to ?? ""}
          onChange={(event) => onChange(from, event.target.value || undefined)}
          className="h-9"
        />
      </div>
    </div>
  );
}

function SearchField({ value, onChange }: { readonly value: string; readonly onChange: (value: string) => void }) {
  const id = useId();

  return (
    <label htmlFor={id} className="relative flex w-full max-w-xs items-center">
      <span className="sr-only">Search documents</span>
      <svg
        className="pointer-events-none absolute left-3 h-4 w-4 text-slate-400"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth="1.5"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.35-4.35m0 0A7.5 7.5 0 1 0 5.25 5.25a7.5 7.5 0 0 0 11.4 11.4Z" />
      </svg>
      <Input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search"
        className="h-9 pl-9"
      />
    </label>
  );
}
