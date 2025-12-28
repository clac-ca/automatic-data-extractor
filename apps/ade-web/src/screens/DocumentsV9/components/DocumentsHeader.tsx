import { type ChangeEvent, type MutableRefObject } from "react";
import clsx from "clsx";

import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

import type { ViewMode } from "../types";
import { BoardIcon, DocumentIcon, GridIcon, SearchIcon, UploadIcon } from "./icons";

export function DocumentsHeader({
  search,
  onSearchChange,
  searchRef,
  viewMode,
  onViewModeChange,
  sort,
  onSortChange,
  onUploadClick,
  fileInputRef,
  onFileInputChange,
  activeViewLabel,
  showSaveView,
  onSaveViewClick,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchRef: MutableRefObject<HTMLInputElement | null>;
  viewMode: ViewMode;
  onViewModeChange: (value: ViewMode) => void;
  sort: string | null;
  onSortChange: (value: string | null) => void;
  onUploadClick: () => void;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  onFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  activeViewLabel: string;
  showSaveView: boolean;
  onSaveViewClick: () => void;
}) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-slate-100 text-slate-700">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-900">Documents</h1>
            <p className="text-xs text-slate-500">{activeViewLabel}</p>
          </div>
        </div>

        <div className="flex min-w-[240px] flex-1 items-center">
          <label className="sr-only" htmlFor="documents-v9-search">
            Search documents
          </label>
          <div className="relative w-full">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <SearchIcon className="h-4 w-4" />
            </span>
            <Input
              id="documents-v9-search"
              ref={searchRef}
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search by filename, uploader, or tag"
              className="pl-9"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm md:flex">
            <span className="text-slate-500">Sort</span>
            <select
              value={sort ?? ""}
              onChange={(e) => onSortChange(e.target.value || null)}
              aria-label="Sort documents"
              className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
            >
              <option value="-created_at">Newest</option>
              <option value="created_at">Oldest</option>
              <option value="name">Name (A–Z)</option>
              <option value="-last_run_at">Recently processed</option>
            </select>
          </div>

          {showSaveView ? (
            <Button type="button" size="sm" variant="secondary" onClick={onSaveViewClick}>
              Save view
            </Button>
          ) : null}

          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 shadow-sm">
            <Button
              type="button"
              size="sm"
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("grid")}
              className={clsx("rounded-md", viewMode === "grid" ? "shadow-sm" : "text-slate-500")}
              aria-pressed={viewMode === "grid"}
              aria-label="Grid view"
            >
              <GridIcon className="h-4 w-4" />
              Grid
            </Button>
            <Button
              type="button"
              size="sm"
              variant={viewMode === "board" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("board")}
              className={clsx("rounded-md", viewMode === "board" ? "shadow-sm" : "text-slate-500")}
              aria-pressed={viewMode === "board"}
              aria-label="Board view"
            >
              <BoardIcon className="h-4 w-4" />
              Board
            </Button>
          </div>

          <Button type="button" onClick={onUploadClick} size="md" className="gap-2">
            <UploadIcon className="h-4 w-4" />
            Upload
          </Button>
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onFileInputChange} />
        </div>
      </div>
    </header>
  );
}
