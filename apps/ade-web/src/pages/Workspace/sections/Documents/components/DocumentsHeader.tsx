import { type ChangeEvent, type MutableRefObject } from "react";

import type { DocumentUploadResponse } from "@api/documents";
import type { UploadManagerItem, UploadManagerSummary } from "@hooks/documents/uploadManager";
import { Button } from "@components/ui/button";

import { ConfigurationBanner } from "./ConfigurationBanner";
import { ProcessingPausedBanner } from "./ProcessingPausedBanner";
import { UploadManager } from "./UploadManager";
import { DocumentIcon, UploadIcon } from "@components/icons";

export function DocumentsHeader({
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
  return (
    <header className="shrink-0 border-b border-border bg-gradient-to-b from-card via-card to-background/60 shadow-sm">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-background text-foreground shadow-sm">
            <DocumentIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-foreground">Documents</h1>
            <p className="text-xs text-muted-foreground">Shared team workspace for processing.</p>
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-3">
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
