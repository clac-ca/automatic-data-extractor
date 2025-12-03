export type BuildStatus = "queued" | "building" | "ready" | "failed" | "cancelled";

// Build streaming now uses the unified AdeEvent envelope. Helpers live in
// @shared/runs/types (AdeEvent + type guards). This file keeps the status union.
