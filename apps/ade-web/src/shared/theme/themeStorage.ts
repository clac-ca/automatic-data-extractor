export type ThemePreference = "system" | "light" | "dark";

export const THEME_STORAGE_KEY = "ade.ui.theme.preference";

function readRawPreference(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch (error) {
    console.warn("Failed to read theme preference", error);
    return null;
  }
}

export function readStoredThemePreference(): ThemePreference | null {
  const raw = readRawPreference();
  if (raw === "light" || raw === "dark" || raw === "system") {
    return raw;
  }
  return null;
}

export function writeThemePreference(next: ThemePreference): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch (error) {
    console.warn("Failed to persist theme preference", error);
  }
}
