import { PageState } from "@ui/PageState";

import type { RunRecord } from "../types";

import { RunPreviewPanel } from "./RunPreviewPanel";

export function RunsInspector({
  run,
  open,
  onClose,
}: {
  run: RunRecord | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!run || !open) {
    return (
      <section className="rounded-2xl border border-border bg-card px-6 py-8">
        <PageState
          title="Select a run"
          description="Choose a run from the table to inspect metrics, mappings, and output details."
          variant="empty"
        />
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <RunPreviewPanel run={run} onClose={onClose} />
    </section>
  );
}
