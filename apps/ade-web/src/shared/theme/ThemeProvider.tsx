import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { applyThemeToDocument, resolveTheme, type ThemeId } from "./index";
import { readStoredThemePreference, writeThemePreference, type ThemePreference } from "./themeStorage";

interface ThemeContextValue {
  readonly preference: ThemePreference;
  readonly resolvedTheme: ThemeId;
  readonly systemPrefersDark: boolean;
  readonly setPreference: (next: ThemePreference) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const storedPreference = useMemo(() => readStoredThemePreference(), []);
  const [preference, setPreferenceState] = useState<ThemePreference>(storedPreference ?? "system");
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

    if (preference === "system") {
      if (typeof media.addEventListener === "function") {
        media.addEventListener("change", handleChange);
      } else if (typeof media.addListener === "function") {
        media.addListener(handleChange);
      }
    }

    setSystemPrefersDark(media.matches);

    return () => {
      if (typeof media.removeEventListener === "function") {
        media.removeEventListener("change", handleChange);
      } else if (typeof media.removeListener === "function") {
        media.removeListener(handleChange);
      }
    };
  }, [preference]);

  const resolvedTheme = useMemo(() => resolveTheme(preference, systemPrefersDark), [preference, systemPrefersDark]);

  useEffect(() => {
    applyThemeToDocument(resolvedTheme);
  }, [resolvedTheme]);

  useEffect(() => {
    writeThemePreference(preference);
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
  }, []);

  const value = useMemo(
    () => ({
      preference,
      resolvedTheme,
      systemPrefersDark,
      setPreference,
    }),
    [preference, resolvedTheme, setPreference, systemPrefersDark],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
