import { type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { SpinnerIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { PresenceConnectionState, PresenceParticipant } from "@/types/presence";

import type { DocumentViewRecord } from "@/api/documents/views";
import { DocumentsPresenceIndicator } from "../../shared/presence/DocumentsPresenceIndicator";

type DocumentViewsToolbarModel = {
  selectedView: DocumentViewRecord | null;
  isEdited: boolean;
  error: string | null;
  hasExplicitListState: boolean;
  canMutateSelectedView: boolean;
  isSaving: boolean;
  isCreating: boolean;
  isDeleting: boolean;
};

export function DocumentsToolbar({
  participants,
  connectionState,
  configMissing,
  processingPaused,
  hasDocuments,
  isListFetching,
  hasListError,
  views,
  toolbarActions,
  onOpenSaveAs,
  onSaveSelectedView,
  onDiscardViewChanges,
}: {
  participants: PresenceParticipant[];
  connectionState: PresenceConnectionState;
  configMissing: boolean;
  processingPaused: boolean;
  hasDocuments: boolean;
  isListFetching: boolean;
  hasListError: boolean;
  views: DocumentViewsToolbarModel;
  toolbarActions?: ReactNode;
  onOpenSaveAs: (sourceView?: DocumentViewRecord | null) => void;
  onSaveSelectedView: () => void;
  onDiscardViewChanges: () => void;
}) {
  const showEditedControls = Boolean(views.selectedView && views.isEdited);
  const showCreateFromCurrent = !views.selectedView && views.hasExplicitListState;

  const toolbarStatus = (
    <div className="flex h-4 w-4 items-center justify-center">
      {isListFetching ? (
        <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : hasListError && hasDocuments ? (
        <AlertTriangle className="h-4 w-4 text-destructive" aria-label="Document list refresh failed" />
      ) : null}
    </div>
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <DocumentsPresenceIndicator participants={participants} connectionState={connectionState} />
      {configMissing ? (
        <Badge variant="secondary" className="text-xs">
          No active configuration
        </Badge>
      ) : null}
      {processingPaused ? (
        <Badge variant="secondary" className="text-xs">
          Processing paused
        </Badge>
      ) : null}
      {showEditedControls ? (
        <div className="flex items-center gap-1.5 rounded-md border border-border/70 bg-muted/40 px-2 py-1">
          <Badge variant="secondary" className="h-5 text-[10px] uppercase tracking-wide">
            Edited
          </Badge>
          {views.canMutateSelectedView ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={onSaveSelectedView}
              disabled={views.isSaving || views.isDeleting}
              className="h-7 px-2"
            >
              {views.isSaving ? "Saving..." : "Save"}
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenSaveAs()}
            disabled={views.isCreating || views.isDeleting}
            className="h-7 px-2"
          >
            Save as new
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDiscardViewChanges}
            disabled={views.isSaving || views.isCreating || views.isDeleting}
            className="h-7 px-2"
          >
            Discard
          </Button>
        </div>
      ) : null}
      {showCreateFromCurrent ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => onOpenSaveAs()}
          disabled={views.isCreating || views.isDeleting}
        >
          Save as new view
        </Button>
      ) : null}
      {views.error ? <span className="text-destructive text-xs">{views.error}</span> : null}
      {toolbarActions}
      {toolbarStatus}
    </div>
  );
}
