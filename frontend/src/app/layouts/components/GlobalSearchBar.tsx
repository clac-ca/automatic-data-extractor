import { useState } from "react";

export interface GlobalSearchBarProps {
  readonly placeholder?: string;
  readonly id?: string;
}

export function GlobalSearchBar({ placeholder, id }: GlobalSearchBarProps) {
  const [value, setValue] = useState("");

  return (
    <form
      role="search"
      className="relative w-full max-w-xl"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <label htmlFor={id ?? "global-search"} className="sr-only">
        Search workspace
      </label>
      <input
        id={id ?? "global-search"}
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder ?? "Search documents, runs, members, or actions…"}
        className="w-full rounded-full border border-slate-200 bg-white px-5 py-3 pl-12 text-base text-slate-800 shadow-[0_12px_32px_rgba(15,23,42,0.08)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      />
      <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-slate-400">
        <SearchIcon />
      </span>
      <span className="pointer-events-none absolute inset-y-0 right-5 hidden items-center gap-1 text-xs text-slate-300 sm:flex">
        <kbd className="rounded border border-slate-200 px-1 py-0.5 font-sans text-[11px]">⌘</kbd>
        <kbd className="rounded border border-slate-200 px-1 py-0.5 font-sans text-[11px]">K</kbd>
      </span>
    </form>
  );
}

function SearchIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M8.5 3a5.5 5.5 0 013.934 9.35l3.108 3.107a1 1 0 01-1.414 1.415l-3.108-3.108A5.5 5.5 0 118.5 3zm0 2a3.5 3.5 0 100 7 3.5 3.5 0 000-7z"
        clipRule="evenodd"
      />
    </svg>
  );
}
