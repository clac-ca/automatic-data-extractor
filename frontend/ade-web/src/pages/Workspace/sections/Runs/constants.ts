import type { RunStatus } from "@/types";

export const DEFAULT_PAGE_SIZE = 10;

export const RUNS_SORT_IDS = new Set([
  "id",
  "status",
  "createdAt",
  "startedAt",
  "completedAt",
]);

export const RUNS_FILTER_IDS = new Set([
  "status",
  "configurationId",
  "createdAt",
  "startedAt",
  "completedAt",
  "fileType",
  "hasOutput",
]);

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
    badgeClass: "bg-accent text-accent-foreground",
    dotClass: "bg-accent-foreground",
    ringClass: "ring-accent/50",
    textClass: "text-accent-foreground",
    surfaceClass: "bg-accent",
  },
  succeeded: {
    label: "Success",
    badgeClass: "bg-primary/10 text-primary",
    dotClass: "bg-primary",
    ringClass: "ring-primary/30",
    textClass: "text-primary",
    surfaceClass: "bg-primary/10",
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
