import type { ListDensity, ListPageSize, ListRefreshInterval, ListSettings } from "./types";

export const LIST_PAGE_SIZES: ListPageSize[] = [50, 100, 200, 1000, 2000];

export const LIST_REFRESH_INTERVALS: Array<{
  value: ListRefreshInterval;
  label: string;
  intervalMs: number | false;
}> = [
  { value: "auto", label: "Auto", intervalMs: false },
  { value: "off", label: "Off", intervalMs: false },
  { value: "30s", label: "Every 30s", intervalMs: 30_000 },
  { value: "1m", label: "Every 1m", intervalMs: 60_000 },
  { value: "5m", label: "Every 5m", intervalMs: 300_000 },
];

export const LIST_DENSITIES: Array<{ value: ListDensity; label: string }> = [
  { value: "comfortable", label: "Comfortable" },
  { value: "compact", label: "Compact" },
];

export const DEFAULT_LIST_SETTINGS: ListSettings = {
  pageSize: LIST_PAGE_SIZES[0],
  refreshInterval: "auto",
  density: "comfortable",
};

export function normalizeListSettings(value: Partial<ListSettings> | null | undefined): ListSettings {
  const settings = value ?? {};
  const pageSize = typeof settings.pageSize === "string" ? Number(settings.pageSize) : settings.pageSize;
  return {
    pageSize: isListPageSize(pageSize) ? pageSize : DEFAULT_LIST_SETTINGS.pageSize,
    refreshInterval: isListRefreshInterval(settings.refreshInterval)
      ? settings.refreshInterval
      : DEFAULT_LIST_SETTINGS.refreshInterval,
    density: isListDensity(settings.density) ? settings.density : DEFAULT_LIST_SETTINGS.density,
  };
}

export function resolveRefreshIntervalMs(value: ListRefreshInterval): number | false {
  return LIST_REFRESH_INTERVALS.find((option) => option.value === value)?.intervalMs ?? false;
}

function isListPageSize(value: unknown): value is ListPageSize {
  return LIST_PAGE_SIZES.includes(value as ListPageSize);
}

function isListRefreshInterval(value: unknown): value is ListRefreshInterval {
  return LIST_REFRESH_INTERVALS.some((option) => option.value === value);
}

function isListDensity(value: unknown): value is ListDensity {
  return LIST_DENSITIES.some((option) => option.value === value);
}
