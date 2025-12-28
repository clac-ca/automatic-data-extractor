import type { ModePreference } from "./themeStorage";

export type ThemeId = "default" | (string & {});
export type ResolvedMode = "light" | "dark";

export type { ModePreference };

export const DEFAULT_THEME_ID: ThemeId = "default";

export const MODE_OPTIONS: Array<{
  value: ModePreference;
  label: string;
  description: string;
}> = [
  { value: "system", label: "System", description: "Match your device" },
  { value: "light", label: "Light", description: "Bright and clear" },
  { value: "dark", label: "Dark", description: "Low-light friendly" },
];

export const BUILTIN_THEMES: Array<{
  id: ThemeId;
  label: string;
  description: string;
}> = [{ id: DEFAULT_THEME_ID, label: "Default", description: "Balanced and familiar" }];

export function isDarkMode(mode: ResolvedMode): boolean {
  return mode === "dark";
}

export function resolveMode(preference: ModePreference, systemPrefersDark: boolean): ResolvedMode {
  if (preference === "system") {
    return systemPrefersDark ? "dark" : "light";
  }
  return preference;
}

export function applyThemeToDocument(theme: ThemeId, mode: ResolvedMode): void {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.dataset.mode = mode;
  root.style.colorScheme = isDarkMode(mode) ? "dark" : "light";
}

export { ThemeProvider } from "./ThemeProvider";
export { useTheme } from "./useTheme";
