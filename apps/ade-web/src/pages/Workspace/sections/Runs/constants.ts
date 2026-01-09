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
    badgeClass: "bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-200",
    dotClass: "bg-sky-500",
    ringClass: "ring-sky-200 dark:ring-sky-500/20",
    textClass: "text-sky-700 dark:text-sky-200",
    surfaceClass: "bg-sky-50 dark:bg-sky-500/10",
  },
  succeeded: {
    label: "Success",
    badgeClass: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200",
    dotClass: "bg-emerald-500",
    ringClass: "ring-emerald-200 dark:ring-emerald-500/20",
    textClass: "text-emerald-700 dark:text-emerald-200",
    surfaceClass: "bg-emerald-50 dark:bg-emerald-500/10",
  },
  failed: {
    label: "Failed",
    badgeClass: "bg-destructive/10 text-destructive dark:bg-destructive/20",
    dotClass: "bg-destructive",
    ringClass: "ring-destructive/20 dark:ring-destructive/40",
    textClass: "text-destructive",
    surfaceClass: "bg-destructive/10 dark:bg-destructive/20",
  },
};
