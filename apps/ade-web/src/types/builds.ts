import type { components } from "@schema";

export type BuildStatus = components["schemas"]["BuildStatus"];

// Build streaming reuses the unified EventRecord envelope. Helpers live in
// @schema/runs; this file keeps the API-sourced status union.
