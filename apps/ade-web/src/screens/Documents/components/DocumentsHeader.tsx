import { type ChangeEvent, type MutableRefObject } from "react";
import clsx from "clsx";

import type { DocumentUploadResponse } from "@shared/documents";
import type { UploadManagerItem, UploadManagerSummary } from "@shared/documents/uploadManager";
import { Button } from "@ui/Button";

import { formatRelativeTime } from "../utils";
import type { ListSettings, ViewMode } from "../types";
import { ListSettingsPopover } from "./ListSettingsPopover";
import { ConfigurationBanner } from "./ConfigurationBanner";
import { ProcessingPausedBanner } from "./ProcessingPausedBanner";
import { UploadManager } from "./UploadManager";
import { BoardIcon, DocumentIcon, GridIcon, RefreshIcon, UploadIcon } from "@ui/Icons";

export function DocumentsHeader({
  viewMode,
  onViewModeChange,
  listSettings,
  onListSettingsChange,
  onRefresh,
  isRefreshing,
  lastUpdatedAt,
  now,
  onUploadClick,
  fileInputRef,
  onFileInputChange,
  showConfigurationWarning,
  processingPaused,
  canManageConfigurations,
  canManageSettings,
  onOpenConfigBuilder,
  onOpenSettings,
  uploads,
  onPauseUpload,
  onResumeUpload,
  onRetryUpload,
  onCancelUpload,
  onRemoveUpload,
  onClearCompletedUploads,
}: {
  viewMode: ViewMode;
  onViewModeChange: (value: ViewMode) => void;
  listSettings: ListSettings;
  onListSettingsChange: (next: ListSettings) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  lastUpdatedAt: number | null;
  now: number;
  onUploadClick: () => void;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  onFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  showConfigurationWarning: boolean;
  processingPaused: boolean;
  canManageConfigurations: boolean;
  canManageSettings: boolean;
  onOpenConfigBuilder: () => void;
  onOpenSettings: () => void;
  uploads: {
    items: UploadManagerItem<DocumentUploadResponse>[];
    summary: UploadManagerSummary;
  };
  onPauseUpload: (uploadId: string) => void;
  onResumeUpload: (uploadId: string) => void;
  onRetryUpload: (uploadId: string) => void;
  onCancelUpload: (uploadId: string) => void;
  onRemoveUpload: (uploadId: string) => void;
  onClearCompletedUploads: () => void;
}) {
  const updatedLabel = lastUpdatedAt ? formatRelativeTime(now, lastUpdatedAt) : "—";
  return (
    <header className="shrink-0 border-b border-border bg-card">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-muted text-foreground">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-foreground">Documents</h1>
            <p className="text-xs text-muted-foreground">Shared team workspace for processing.</p>
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <div className="flex items-center rounded-lg border border-border bg-background p-1 text-xs shadow-sm">
            <Button
              type="button"
              size="sm"
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("grid")}
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "grid" ? "shadow-sm" : "text-muted-foreground")}
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
              className={clsx("h-8 rounded-md px-3 text-xs", viewMode === "board" ? "shadow-sm" : "text-muted-foreground")}
              aria-pressed={viewMode === "board"}
              aria-label="Board view"
            >
              <BoardIcon className="h-4 w-4" />
              Board
            </Button>
          </div>

          <ListSettingsPopover settings={listSettings} onChange={onListSettingsChange} />

          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="hidden sm:inline">Updated {updatedLabel}</span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onRefresh}
              className="h-8 rounded-md px-2 text-xs"
              aria-label="Refresh documents"
            >
              <RefreshIcon className={clsx("h-4 w-4", isRefreshing && "animate-spin")} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>

          <UploadManager
            items={uploads.items}
            summary={uploads.summary}
            onPause={onPauseUpload}
            onResume={onResumeUpload}
            onRetry={onRetryUpload}
            onCancel={onCancelUpload}
            onRemove={onRemoveUpload}
            onClearCompleted={onClearCompletedUploads}
          />

          <Button type="button" onClick={onUploadClick} size="md" className="gap-2">
            <UploadIcon className="h-4 w-4" />
            Upload
          </Button>
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onFileInputChange} />
        </div>
      </div>
      {processingPaused ? (
        <div className="border-t border-border px-6 py-3">
          <ProcessingPausedBanner
            canManageSettings={canManageSettings}
            onOpenSettings={onOpenSettings}
            configMissing={showConfigurationWarning}
          />
        </div>
      ) : showConfigurationWarning ? (
        <div className="border-t border-border px-6 py-3">
          <div className="space-y-2">
            <ConfigurationBanner
              canManageConfigurations={canManageConfigurations}
              onOpenConfigBuilder={onOpenConfigBuilder}
            />
          </div>
        </div>
      ) : null}
    </header>
  );
}
