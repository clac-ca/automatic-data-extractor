import type { ThemePreference } from "./themeStorage";

export type ThemeId = "light" | "dark";

export type { ThemePreference };

export const THEME_OPTIONS: Array<{
  value: ThemePreference;
  label: string;
  description: string;
}> = [
  { value: "system", label: "System", description: "Match your device" },
  { value: "light", label: "Light", description: "Bright and clear" },
  { value: "dark", label: "Dark", description: "Low-light friendly" },
];

export function isDarkTheme(theme: ThemeId): boolean {
  return theme === "dark";
}

export function resolveTheme(preference: ThemePreference, systemPrefersDark: boolean): ThemeId {
  if (preference === "system") {
    return systemPrefersDark ? "dark" : "light";
  }
  return preference;
}

export function applyThemeToDocument(theme: ThemeId): void {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = isDarkTheme(theme) ? "dark" : "light";
}

export { ThemeProvider } from "./ThemeProvider";
export { useTheme } from "./useTheme";
