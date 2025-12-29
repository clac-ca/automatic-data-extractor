import { useEffect, useState } from "react";

import { Button } from "@ui/Button";

import { TagPicker } from "./TagPicker";

export function BulkTagDialog({
  open,
  workspaceId,
  selectedCount,
  onClose,
  onApply,
}: {
  open: boolean;
  workspaceId: string;
  selectedCount: number;
  onClose: () => void;
  onApply: (payload: { add: string[]; remove: string[] }) => void;
}) {
  const [addTags, setAddTags] = useState<string[]>([]);
  const [removeTags, setRemoveTags] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    setAddTags([]);
    setRemoveTags([]);
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay/30 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-5 shadow-xl">
        <p className="text-sm font-semibold text-foreground">Bulk tag update</p>
        <p className="mt-1 text-xs text-muted-foreground">Adding to {selectedCount} documents.</p>

        <div className="mt-4 grid gap-4">
          <div>
            <p className="text-xs font-semibold text-muted-foreground">Add tags</p>
            <div className="mt-2">
              <TagPicker
                workspaceId={workspaceId}
                selected={addTags}
                onToggle={(tag) => {
                  setAddTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
                }}
                placeholder={addTags.length ? "Edit add tags" : "Add tags"}
              />
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold text-muted-foreground">Remove tags</p>
            <div className="mt-2">
              <TagPicker
                workspaceId={workspaceId}
                selected={removeTags}
                onToggle={(tag) => {
                  setRemoveTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
                }}
                placeholder={removeTags.length ? "Edit remove tags" : "Remove tags"}
              />
            </div>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => {
              const add = addTags.filter((t) => !removeTags.includes(t));
              const remove = removeTags.filter((t) => !addTags.includes(t));
              if (add.length === 0 && remove.length === 0) return;
              onApply({ add, remove });
              onClose();
            }}
            disabled={addTags.length === 0 && removeTags.length === 0}
          >
            Apply
          </Button>
        </div>
      </div>
    </div>
  );
}
