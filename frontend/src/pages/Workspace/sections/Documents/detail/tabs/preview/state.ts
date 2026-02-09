import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

export type NormalizedPreviewState =
  | { available: true; reason: null }
  | { available: false; reason: string };

export function getNormalizedPreviewState(
  document: DocumentRow,
): NormalizedPreviewState {
  const lastRun = document.lastRun;
  if (!lastRun) {
    return {
      available: false,
      reason: "No runs have completed for this document yet.",
    };
  }

  if (lastRun.status === "succeeded") {
    return { available: true, reason: null };
  }

  if (lastRun.status === "running" || lastRun.status === "queued") {
    return {
      available: false,
      reason: "The latest run is still in progress. Normalized output is not ready yet.",
    };
  }

  if (lastRun.status === "cancelled") {
    return {
      available: false,
      reason: "The latest run was cancelled. Normalized output is unavailable until a run succeeds.",
    };
  }

  return {
    available: false,
    reason:
      lastRun.errorMessage?.trim() ||
      "The latest run failed. Normalized output is unavailable until a run succeeds.",
  };
}
