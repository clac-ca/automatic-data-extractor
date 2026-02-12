import { useEffect, useState } from "react";
import type { Theme } from "@glideapps/glide-data-grid";

import { useTheme } from "@/providers/theme";

import { resolveCssRgbaColor } from "./cssColor";

type GlideThemeTokenMap = {
  field: keyof Theme;
  variable: string;
  fallback: string;
};

const GLIDE_THEME_TOKEN_MAP: readonly GlideThemeTokenMap[] = [
  { field: "accentColor", variable: "--primary", fallback: "#4F5DFF" },
  { field: "accentFg", variable: "--primary-foreground", fallback: "#FFFFFF" },
  { field: "accentLight", variable: "--accent", fallback: "rgba(62, 116, 253, 0.1)" },
  { field: "textDark", variable: "--foreground", fallback: "#313139" },
  { field: "textMedium", variable: "--muted-foreground", fallback: "#737383" },
  { field: "textLight", variable: "--muted-foreground", fallback: "#B2B2C0" },
  { field: "textBubble", variable: "--foreground", fallback: "#313139" },
  { field: "bgIconHeader", variable: "--muted-foreground", fallback: "#737383" },
  { field: "fgIconHeader", variable: "--background", fallback: "#FFFFFF" },
  { field: "textHeader", variable: "--foreground", fallback: "#313139" },
  { field: "textHeaderSelected", variable: "--primary-foreground", fallback: "#FFFFFF" },
  { field: "bgCell", variable: "--background", fallback: "#FFFFFF" },
  { field: "bgCellMedium", variable: "--muted", fallback: "#FAFAFB" },
  { field: "bgHeader", variable: "--card", fallback: "#F7F7F8" },
  { field: "bgHeaderHasFocus", variable: "--accent", fallback: "#E9E9EB" },
  { field: "bgHeaderHovered", variable: "--accent", fallback: "#EFEFF1" },
  { field: "bgBubble", variable: "--secondary", fallback: "#EDEDF3" },
  { field: "bgBubbleSelected", variable: "--background", fallback: "#FFFFFF" },
  { field: "bgSearchResult", variable: "--accent", fallback: "#fff9e3" },
  { field: "borderColor", variable: "--border", fallback: "rgba(115, 116, 131, 0.16)" },
  { field: "horizontalBorderColor", variable: "--border", fallback: "rgba(115, 116, 131, 0.16)" },
  { field: "drilldownBorder", variable: "--ring", fallback: "rgba(0, 0, 0, 0)" },
  { field: "linkColor", variable: "--primary", fallback: "#353fb5" },
];

export function useGlideDataEditorTheme(): Partial<Theme> {
  const { theme, resolvedMode } = useTheme();
  const [paletteTheme, setPaletteTheme] = useState<Partial<Theme>>(() => buildFallbackTheme());

  useEffect(() => {
    setPaletteTheme(buildThemeFromCssTokens());
  }, [resolvedMode, theme]);

  useEffect(() => {
    if (typeof MutationObserver === "undefined" || typeof document === "undefined") {
      return;
    }
    const root = document.documentElement;
    if (!root) {
      return;
    }
    const observer = new MutationObserver(() => {
      setPaletteTheme(buildThemeFromCssTokens());
    });
    observer.observe(root, { attributes: true, attributeFilter: ["class", "data-theme"] });
    return () => observer.disconnect();
  }, []);

  return paletteTheme;
}

function buildThemeFromCssTokens(): Partial<Theme> {
  return GLIDE_THEME_TOKEN_MAP.reduce<Partial<Theme>>((acc, tokenMap) => {
    acc[tokenMap.field] = resolveCssRgbaColor(tokenMap.variable, tokenMap.fallback);
    return acc;
  }, {});
}

function buildFallbackTheme(): Partial<Theme> {
  return GLIDE_THEME_TOKEN_MAP.reduce<Partial<Theme>>((acc, tokenMap) => {
    acc[tokenMap.field] = tokenMap.fallback;
    return acc;
  }, {});
}
