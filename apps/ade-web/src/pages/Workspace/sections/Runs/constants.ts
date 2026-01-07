import type { RunStatus } from "@schema";

import type { RunsFilters } from "./types";

export const DEFAULT_RUNS_FILTERS: RunsFilters = {
  search: "",
  status: "all",
  dateRange: "14d",
  configurationId: null,
};

export const DATE_RANGE_OPTIONS: { value: RunsFilters["dateRange"]; label: string }[] = [
  { value: "14d", label: "Last 14 days" },
  { value: "7d", label: "Last 7 days" },
  { value: "24h", label: "Last 24 hours" },
  { value: "30d", label: "Last 30 days" },
  { value: "custom", label: "Custom range" },
];

export const RUN_STATUS_META: Record<
  RunStatus,
  {
    readonly label: string;
    readonly badgeClass: string;
    readonly dotClass: string;
    readonly ringClass: string;
    readonly textClass: string;
    readonly surfaceClass: string;
  }
> = {
  queued: {
    label: "Queued",
    badgeClass: "bg-muted text-muted-foreground",
    dotClass: "bg-muted-foreground",
    ringClass: "ring-border",
    textClass: "text-muted-foreground",
    surfaceClass: "bg-muted",
  },
  running: {
    label: "Running",
    badgeClass: "bg-info-100 text-info-700",
    dotClass: "bg-info-500",
    ringClass: "ring-info-200",
    textClass: "text-info-700",
    surfaceClass: "bg-info-50",
  },
  succeeded: {
    label: "Success",
    badgeClass: "bg-success-100 text-success-700",
    dotClass: "bg-success-500",
    ringClass: "ring-success-200",
    textClass: "text-success-700",
    surfaceClass: "bg-success-50",
  },
  failed: {
    label: "Failed",
    badgeClass: "bg-danger-100 text-danger-700",
    dotClass: "bg-danger-500",
    ringClass: "ring-danger-200",
    textClass: "text-danger-700",
    surfaceClass: "bg-danger-50",
  },
};
