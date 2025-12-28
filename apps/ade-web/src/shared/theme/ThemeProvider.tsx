import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { applyThemeToDocument, resolveMode, DEFAULT_THEME_ID, type ResolvedMode, type ThemeId } from "./index";
import {
  MODE_STORAGE_KEY,
  THEME_STORAGE_KEY,
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
  readonly setModePreference: (next: ModePreference) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const storedMode = useMemo(() => readStoredModePreference(), []);
  const storedTheme = useMemo(() => readStoredThemePreference(), []);
  const [modePreference, setModePreferenceState] = useState<ModePreference>(storedMode ?? "system");
  const [theme, setThemeState] = useState<ThemeId>(storedTheme ?? DEFAULT_THEME_ID);
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

  useEffect(() => {
    applyThemeToDocument(theme, resolvedMode);
  }, [resolvedMode, theme]);

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
        const next = event.newValue;
        if (next === "light" || next === "dark" || next === "system") {
          setModePreferenceState(next);
        } else if (next === null) {
          setModePreferenceState("system");
        }
        return;
      }
      if (event.key === THEME_STORAGE_KEY) {
        const next = event.newValue;
        if (typeof next === "string" && next.length > 0) {
          setThemeState(next as ThemeId);
        } else if (next === null) {
          setThemeState(DEFAULT_THEME_ID);
        }
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const setTheme = useCallback((next: ThemeId) => {
    setThemeState(next);
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
      setModePreference,
    }),
    [modePreference, resolvedMode, setModePreference, setTheme, systemPrefersDark, theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
