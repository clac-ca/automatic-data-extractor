import type { DocumentViewRecord } from "@/api/documents/views";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function DocumentsDialogs({
  saveAsOpen,
  onSaveAsOpenChange,
  saveAsName,
  onSaveAsNameChange,
  saveAsVisibility,
  onSaveAsVisibilityChange,
  saveAsError,
  canManagePublicViews,
  isCreatingView,
  onCloseSaveAs,
  onSaveAsNewView,
  viewRenameTarget,
  viewRenameName,
  onViewRenameNameChange,
  viewRenameError,
  isViewRenameSubmitting,
  onCloseRenameView,
  onConfirmRenameView,
  viewDeleteTarget,
  isViewDeleteSubmitting,
  onCloseDeleteView,
  onConfirmDeleteView,
}: {
  saveAsOpen: boolean;
  onSaveAsOpenChange: (open: boolean) => void;
  saveAsName: string;
  onSaveAsNameChange: (value: string) => void;
  saveAsVisibility: "private" | "public";
  onSaveAsVisibilityChange: (value: "private" | "public") => void;
  saveAsError: string | null;
  canManagePublicViews: boolean;
  isCreatingView: boolean;
  onCloseSaveAs: () => void;
  onSaveAsNewView: () => void;
  viewRenameTarget: DocumentViewRecord | null;
  viewRenameName: string;
  onViewRenameNameChange: (value: string) => void;
  viewRenameError: string | null;
  isViewRenameSubmitting: boolean;
  onCloseRenameView: () => void;
  onConfirmRenameView: () => void;
  viewDeleteTarget: DocumentViewRecord | null;
  isViewDeleteSubmitting: boolean;
  onCloseDeleteView: () => void;
  onConfirmDeleteView: () => void;
}) {
  return (
    <>
      <Dialog open={saveAsOpen} onOpenChange={onSaveAsOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save as new view</DialogTitle>
            <DialogDescription>
              Create a new saved view from the current filters, sort, lifecycle, and table columns.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="documents-view-name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="documents-view-name"
                value={saveAsName}
                onChange={(event) => onSaveAsNameChange(event.target.value)}
                placeholder="View name"
                autoFocus
                disabled={isCreatingView}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="documents-view-visibility" className="text-sm font-medium">
                Visibility
              </label>
              <Select
                value={saveAsVisibility}
                onValueChange={(next) => onSaveAsVisibilityChange(next as "private" | "public")}
                disabled={isCreatingView}
              >
                <SelectTrigger id="documents-view-visibility">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="private">Private (only me)</SelectItem>
                  <SelectItem value="public" disabled={!canManagePublicViews}>
                    Public (workspace)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            {saveAsError ? <p className="text-destructive text-xs">{saveAsError}</p> : null}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={onCloseSaveAs} disabled={isCreatingView}>
              Cancel
            </Button>
            <Button onClick={onSaveAsNewView} disabled={isCreatingView}>
              {isCreatingView ? "Saving..." : "Save view"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(viewRenameTarget)} onOpenChange={(open) => (!open ? onCloseRenameView() : undefined)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename view</DialogTitle>
            <DialogDescription>Update this saved view name.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label htmlFor="documents-view-rename" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="documents-view-rename"
              value={viewRenameName}
              onChange={(event) => onViewRenameNameChange(event.target.value)}
              placeholder="View name"
              autoFocus
              disabled={isViewRenameSubmitting}
            />
            {viewRenameError ? <p className="text-destructive text-xs">{viewRenameError}</p> : null}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={onCloseRenameView} disabled={isViewRenameSubmitting}>
              Cancel
            </Button>
            <Button onClick={onConfirmRenameView} disabled={isViewRenameSubmitting}>
              {isViewRenameSubmitting ? "Renaming..." : "Rename"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(viewDeleteTarget)} onOpenChange={(open) => (!open ? onCloseDeleteView() : undefined)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete view?</DialogTitle>
            <DialogDescription>
              {viewDeleteTarget
                ? `Delete "${viewDeleteTarget.name}" from this workspace.`
                : "Delete this saved view."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={onCloseDeleteView} disabled={isViewDeleteSubmitting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={onConfirmDeleteView} disabled={isViewDeleteSubmitting}>
              {isViewDeleteSubmitting ? "Deleting..." : "Delete view"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
