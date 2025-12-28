export type ModePreference = "system" | "light" | "dark";

export const MODE_STORAGE_KEY = "ade.mode";
export const THEME_STORAGE_KEY = "ade.theme";

function readRawPreference(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn("Failed to read theme preference", error);
    return null;
  }
}

export function readStoredModePreference(): ModePreference | null {
  const raw = readRawPreference(MODE_STORAGE_KEY);
  if (raw === "light" || raw === "dark" || raw === "system") {
    return raw;
  }
  return null;
}

export function readStoredThemePreference(): string | null {
  const raw = readRawPreference(THEME_STORAGE_KEY);
  if (typeof raw === "string" && raw.length > 0) {
    return raw;
  }
  return null;
}

export function writeModePreference(next: ModePreference): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(MODE_STORAGE_KEY, next);
  } catch (error) {
    console.warn("Failed to persist theme mode", error);
  }
}

export function writeThemePreference(next: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch (error) {
    console.warn("Failed to persist theme name", error);
  }
}
