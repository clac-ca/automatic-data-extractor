export type BuildStatus = "queued" | "building" | "ready" | "failed" | "cancelled";

// Build streaming reuses the unified EventRecord envelope. Helpers live in
// @shared/runs/types; this file only keeps the status union.
