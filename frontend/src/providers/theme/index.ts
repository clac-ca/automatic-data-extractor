import {
  BUILT_IN_THEMES,
  THEME_IDS,
  isThemeId,
  type BuiltInTheme,
  type ThemeId,
} from "./themes";
import type { ModePreference } from "./themeStorage";
import type { SetModePreferenceOptions } from "./modeTransition";

export type ResolvedMode = "light" | "dark";

export type { ModePreference };
export type { ThemeId };
export type { SetModePreferenceOptions };

export const DEFAULT_THEME_ID: ThemeId = "default";
export const BUILTIN_THEME_IDS = THEME_IDS satisfies readonly ThemeId[];

export const MODE_OPTIONS: Array<{
  value: ModePreference;
  label: string;
  description: string;
}> = [
  { value: "system", label: "System", description: "Match your device" },
  { value: "light", label: "Light", description: "Bright and clear" },
  { value: "dark", label: "Dark", description: "Low-light friendly" },
];

export const BUILTIN_THEMES = BUILT_IN_THEMES satisfies BuiltInTheme[];

export type { BuiltInTheme };

export function isDarkMode(mode: ResolvedMode): boolean {
  return mode === "dark";
}

export function resolveMode(preference: ModePreference, systemPrefersDark: boolean): ResolvedMode {
  if (preference === "system") {
    return systemPrefersDark ? "dark" : "light";
  }
  return preference;
}

export function normalizeThemeId(value: string | null | undefined): ThemeId {
  if (!value) {
    return DEFAULT_THEME_ID;
  }
  if (isThemeId(value)) {
    return value;
  }
  return DEFAULT_THEME_ID;
}

export function applyThemeToDocument(theme: ThemeId, mode: ResolvedMode): void {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.classList.toggle("dark", isDarkMode(mode));
  root.classList.toggle("light", !isDarkMode(mode));
  root.style.colorScheme = isDarkMode(mode) ? "dark" : "light";
  root.removeAttribute("data-mode");
}

export { ThemeProvider } from "./ThemeProvider";
export { useTheme } from "./useTheme";
export {
  DEFAULT_MODE_TRANSITION_DURATION_MS,
  THEME_MODE_ANCHOR_ATTR,
  WORKSPACE_THEME_MODE_ANCHOR,
} from "./modeTransition";
