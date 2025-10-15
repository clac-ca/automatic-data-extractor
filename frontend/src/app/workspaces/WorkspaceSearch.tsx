import { useState } from "react";

import { Input } from "../../ui";

export function WorkspaceSearch() {
  const [value, setValue] = useState("");

  return (
    <form
      role="search"
      className="relative hidden md:block"
      onSubmit={(event) => {
        event.preventDefault();
        // TODO: wire to real search endpoint
      }}
    >
      <label htmlFor="workspace-search" className="sr-only">
        Search workspace
      </label>
      <Input
        id="workspace-search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search documents, jobs…"
        className="w-64 pl-9 pr-3"
      />
      <span className="pointer-events-none absolute inset-y-0 left-2 flex items-center text-slate-400">
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path
            fillRule="evenodd"
            d="M8.5 3a5.5 5.5 0 013.934 9.35l3.108 3.107a1 1 0 01-1.414 1.415l-3.108-3.108A5.5 5.5 0 118.5 3zm0 2a3.5 3.5 0 100 7 3.5 3.5 0 000-7z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    </form>
  );
}
