const THEME_CONFIG = {
  indigo: { label: "Indigo", description: "Indigo accent on clean neutrals." },
  cyan: { label: "Cyan", description: "Cyan accent — crisp and modern." },
  emerald: { label: "Emerald", description: "Emerald accent — calm and grounded." },
  amber: { label: "Amber", description: "Amber accent — warm and energetic." },
  coral: { label: "Coral", description: "Coral accent — bold and expressive." },
  violet: { label: "Violet", description: "Violet accent — premium and creative." },
  teal: { label: "Teal", description: "Teal accent — bright and balanced." },
  blue: { label: "Blue", description: "Blue accent — minimal and enterprise." },
} as const

export type ThemeId = keyof typeof THEME_CONFIG

export const LEGACY_THEME_ID_ALIASES: Partial<Record<string, ThemeId>> = {
  default: "indigo",
  ocean: "cyan",
  forest: "emerald",
  sunset: "amber",
  rose: "coral",
  grape: "violet",
  sand: "teal",
  carbon: "blue",
} as const

export type BuiltInTheme = {
  id: ThemeId
  label: string
  description: string
}

export const THEME_IDS = Object.keys(THEME_CONFIG) as ThemeId[]

export const BUILT_IN_THEMES: BuiltInTheme[] = THEME_IDS.map((id) => ({
  id,
  ...THEME_CONFIG[id],
}))

export function isThemeId(value: string): value is ThemeId {
  return Object.prototype.hasOwnProperty.call(THEME_CONFIG, value)
}
