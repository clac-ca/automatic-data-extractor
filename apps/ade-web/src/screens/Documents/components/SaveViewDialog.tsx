import { useEffect, useState } from "react";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

export function SaveViewDialog({
  open,
  onClose,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
}) {
  const [name, setName] = useState("");

  useEffect(() => {
    if (open) setName("");
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay/30 px-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-5 shadow-xl">
        <p className="text-sm font-semibold text-foreground">Save view</p>
        <p className="mt-1 text-xs text-muted-foreground">Save your current filters as a reusable view.</p>

        <div className="mt-4">
          <label className="text-xs font-semibold text-muted-foreground">View name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. My triage queue"
            className="mt-2"
            autoFocus
          />
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => {
              const trimmed = name.trim();
              if (!trimmed) return;
              onSave(trimmed);
              setName("");
              onClose();
            }}
            disabled={!name.trim()}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
