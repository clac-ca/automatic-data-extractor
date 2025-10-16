import { useId } from "react";

import { Button, Input, Select } from "../../../../ui";
import { OWNER_FILTER_OPTIONS, STATUS_FILTER_OPTIONS } from "../utils";
import type { OwnerFilterValue, StatusFilterValue } from "../utils";

interface DocumentsToolbarProps {
  readonly owner: OwnerFilterValue;
  readonly onOwnerChange: (value: OwnerFilterValue) => void;
  readonly status: StatusFilterValue;
  readonly onStatusChange: (value: StatusFilterValue) => void;
  readonly search: string;
  readonly onSearchChange: (value: string) => void;
  readonly onUploadClick: () => void;
  readonly isUploading: boolean;
  readonly resultCount: number;
  readonly totalCount: number;
}

export function DocumentsToolbar({
  owner,
  onOwnerChange,
  status,
  onStatusChange,
  search,
  onSearchChange,
  onUploadClick,
  isUploading,
  resultCount,
  totalCount,
}: DocumentsToolbarProps) {
  const showTotal = totalCount > 0 && totalCount !== resultCount;
  const formattedCurrent = resultCount.toLocaleString();
  const formattedTotal = totalCount.toLocaleString();
  const label = showTotal ? `${formattedCurrent} of ${formattedTotal}` : formattedCurrent;
  const noun = resultCount === 1 ? "result" : "results";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
      <div className="flex flex-1 flex-wrap items-center gap-3">
        <FilterSelect
          label="Showing"
          value={owner}
          onChange={onOwnerChange}
          options={OWNER_FILTER_OPTIONS}
          widthClass="w-44"
        />
        <FilterSelect
          label="Status"
          value={status}
          onChange={onStatusChange}
          options={STATUS_FILTER_OPTIONS}
          widthClass="w-48"
        />
        <SearchField value={search} onChange={onSearchChange} />
      </div>
      <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        <span aria-live="polite">
          {label} {noun}
        </span>
        <Button onClick={onUploadClick} isLoading={isUploading} size="sm">
          Upload
        </Button>
      </div>
    </div>
  );
}

type Option<T extends string> = { value: T; label: string };

interface FilterSelectProps<T extends string> {
  readonly label: string;
  readonly value: T;
  readonly onChange: (value: T) => void;
  readonly options: readonly Option<T>[];
  readonly widthClass: string;
}

function FilterSelect<T extends string>({ label, value, onChange, options, widthClass }: FilterSelectProps<T>) {
  const id = useId();

  return (
    <label htmlFor={id} className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
      <span>{label}</span>
      <Select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className={widthClass}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    </label>
  );
}

interface SearchFieldProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
}

function SearchField({ value, onChange }: SearchFieldProps) {
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
