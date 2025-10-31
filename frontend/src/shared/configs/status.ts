import type { ConfigRecord } from "./types";

export type ConfigStatus = ConfigRecord["status"];

const STATUS_LABELS: Record<ConfigStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  archived: "Archived",
};

const STATUS_TONE_CLASSES: Record<ConfigStatus, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  inactive: "border-sky-200 bg-sky-50 text-sky-700",
  archived: "border-slate-200 bg-slate-50 text-slate-600",
};

export function getConfigStatusLabel(status: ConfigStatus) {
  return STATUS_LABELS[status] ?? status;
}

export function getConfigStatusToneClasses(status: ConfigStatus) {
  return STATUS_TONE_CLASSES[status] ?? STATUS_TONE_CLASSES.inactive;
}
