import { createScopedStorage } from "@lib@/lib/storage";
import { uiStorageKeys } from "@lib@/lib/uiStorageKeys";

export type ModePreference = "system" | "light" | "dark";

export const MODE_STORAGE_KEY = uiStorageKeys.themeMode;
export const THEME_STORAGE_KEY = uiStorageKeys.themeName;

const modeStorage = createScopedStorage(MODE_STORAGE_KEY);
const themeStorage = createScopedStorage(THEME_STORAGE_KEY);

function readRawPreference(storage: ReturnType<typeof createScopedStorage>): string | null {
  return storage.get<string>();
}

export function parseStoredPreference(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === "string" ? parsed : null;
  } catch (error) {
    console.warn("Failed to parse theme preference", error);
    return null;
  }
}

export function readStoredModePreference(): ModePreference | null {
  const raw = readRawPreference(modeStorage);
  if (raw === "light" || raw === "dark" || raw === "system") {
    return raw;
  }
  return null;
}

export function readStoredThemePreference(): string | null {
  const raw = readRawPreference(themeStorage);
  if (typeof raw === "string" && raw.length > 0) {
    return raw;
  }
  return null;
}

export function writeModePreference(next: ModePreference): void {
  modeStorage.set(next);
}

export function writeThemePreference(next: string): void {
  themeStorage.set(next);
}
