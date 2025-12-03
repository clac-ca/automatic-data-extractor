export type BuildStatus = "queued" | "building" | "ready" | "failed" | "canceled";

// Build streaming now uses the unified AdeEvent envelope. Helpers live in
// @shared/runs/types (AdeEvent + type guards). This file keeps the status union.
