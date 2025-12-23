import type { components } from "@schema";

export type BuildStatus = components["schemas"]["BuildStatus"];

// Build streaming reuses the unified EventRecord envelope. Helpers live in
// @shared/runs/types; this file keeps the API-sourced status union.
