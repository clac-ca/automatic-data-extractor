import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { applyThemeToDocument, normalizeThemeId, resolveMode, DEFAULT_THEME_ID, type ResolvedMode, type ThemeId } from "./index";
import {
  MODE_STORAGE_KEY,
  THEME_STORAGE_KEY,
  parseStoredPreference,
  readStoredModePreference,
  readStoredThemePreference,
  writeModePreference,
  writeThemePreference,
  type ModePreference,
} from "./themeStorage";

interface ThemeContextValue {
  readonly theme: ThemeId;
  readonly modePreference: ModePreference;
  readonly resolvedMode: ResolvedMode;
  readonly systemPrefersDark: boolean;
  readonly setTheme: (next: ThemeId) => void;
  readonly setPreviewTheme: (next: ThemeId | null) => void;
  readonly setModePreference: (next: ModePreference) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const [modePreference, setModePreferenceState] = useState<ModePreference>(() => readStoredModePreference() ?? "light");
  const [theme, setThemeState] = useState<ThemeId>(() => normalizeThemeId(readStoredThemePreference()));
  const [previewTheme, setPreviewThemeState] = useState<ThemeId | null>(null);
  const [systemPrefersDark, setSystemPrefersDark] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return false;
    }
    return window.matchMedia(DARK_MODE_QUERY).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const media = window.matchMedia(DARK_MODE_QUERY);
    const handleChange = (event: MediaQueryListEvent) => {
      setSystemPrefersDark(event.matches);
    };

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", handleChange);
    } else if (typeof media.addListener === "function") {
      media.addListener(handleChange);
    }

    setSystemPrefersDark(media.matches);

    return () => {
      if (typeof media.removeEventListener === "function") {
        media.removeEventListener("change", handleChange);
      } else if (typeof media.removeListener === "function") {
        media.removeListener(handleChange);
      }
    };
  }, []);

  const resolvedMode = useMemo(
    () => resolveMode(modePreference, systemPrefersDark),
    [modePreference, systemPrefersDark],
  );

  const effectiveTheme = previewTheme ?? theme;

  useEffect(() => {
    applyThemeToDocument(effectiveTheme, resolvedMode);
  }, [effectiveTheme, resolvedMode]);

  useEffect(() => {
    writeThemePreference(theme);
  }, [theme]);

  useEffect(() => {
    writeModePreference(modePreference);
  }, [modePreference]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.key === MODE_STORAGE_KEY) {
        const next = parseStoredPreference(event.newValue);
        if (next === "light" || next === "dark" || next === "system") {
          setModePreferenceState(next);
        } else if (next === null) {
          setModePreferenceState("light");
        }
        return;
      }
      if (event.key === THEME_STORAGE_KEY) {
        const next = parseStoredPreference(event.newValue);
        if (typeof next === "string") {
          setThemeState(normalizeThemeId(next));
          setPreviewThemeState(null);
        } else if (next === null) {
          setThemeState(DEFAULT_THEME_ID);
          setPreviewThemeState(null);
        }
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const setTheme = useCallback((next: ThemeId) => {
    setThemeState(next);
    setPreviewThemeState(null);
  }, []);

  const setPreviewTheme = useCallback((next: ThemeId | null) => {
    setPreviewThemeState(next);
  }, []);

  const setModePreference = useCallback((next: ModePreference) => {
    setModePreferenceState(next);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      modePreference,
      resolvedMode,
      systemPrefersDark,
      setTheme,
      setPreviewTheme,
      setModePreference,
    }),
    [modePreference, resolvedMode, setModePreference, setPreviewTheme, setTheme, systemPrefersDark, theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
