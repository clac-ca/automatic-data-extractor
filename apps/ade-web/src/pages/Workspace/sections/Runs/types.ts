import type { components, RunResource, RunStatus } from "@schema";

export type RunMetrics = components["schemas"]["RunMetricsResource"];
export type RunField = components["schemas"]["RunFieldResource"];
export type RunColumn = components["schemas"]["RunColumnResource"];

export type RunsStatusFilter = "all" | RunStatus;
export type RunsDateRange = "14d" | "7d" | "24h" | "30d" | "custom";

export interface RunsFilters {
  readonly search: string;
  readonly status: RunsStatusFilter;
  readonly dateRange: RunsDateRange;
  readonly configurationId: string | null;
}

export type RunConfigOption = {
  id: string;
  label: string;
};

export interface RunsCounts {
  readonly total: number;
  readonly success: number;
  readonly warning: number | null;
  readonly failed: number;
  readonly running: number;
  readonly queued: number;
  readonly cancelled: number;
  readonly active: number;
}

export interface RunRecord {
  readonly id: string;
  readonly configurationId: string;
  readonly status: RunStatus;
  readonly inputName: string;
  readonly outputName: string | null;
  readonly configLabel: string;
  readonly startedAtLabel: string;
  readonly durationLabel: string;
  readonly rows: number | null;
  readonly warnings: number | null;
  readonly errors: number | null;
  readonly quality: number | null;
  readonly ownerLabel: string;
  readonly triggerLabel: string;
  readonly engineLabel: string;
  readonly regionLabel: string;
  readonly notes?: string | null;
  readonly raw: RunResource;
}
