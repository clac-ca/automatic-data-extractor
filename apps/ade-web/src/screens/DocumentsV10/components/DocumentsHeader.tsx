import { type ChangeEvent, type MutableRefObject } from "react";
import clsx from "clsx";

import { Button } from "@ui/Button";

import type { ViewMode } from "../types";
import { BoardIcon, DocumentIcon, GridIcon, UploadIcon } from "./icons";

export function DocumentsHeader({
  viewMode,
  onViewModeChange,
  onUploadClick,
  fileInputRef,
  onFileInputChange,
}: {
  viewMode: ViewMode;
  onViewModeChange: (value: ViewMode) => void;
  onUploadClick: () => void;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  onFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <header className="shrink-0 border-b border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-slate-100 text-slate-700">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-900">Documents</h1>
            <p className="text-xs text-slate-500">Shared team workspace for processing and collaboration</p>
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs shadow-sm">
            <Button
              type="button"
              size="sm"
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("grid")}
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "grid" ? "shadow-sm" : "text-slate-500")}
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
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "board" ? "shadow-sm" : "text-slate-500")}
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
