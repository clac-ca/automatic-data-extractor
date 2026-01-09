const THEME_CONFIG = {
  default: { label: "Default", description: "Indigo accent on clean neutrals." },
  ocean: { label: "Ocean", description: "Cyan/teal accent — crisp and modern." },
  forest: { label: "Forest", description: "Emerald accent — calm and grounded." },
  sunset: { label: "Sunset", description: "Orange accent — warm and energetic." },
  rose: { label: "Rose", description: "Rose accent — bold and expressive." },
  grape: { label: "Grape", description: "Violet accent — premium and creative." },
  sand: { label: "Sand", description: "Teal accent on warm neutrals." },
  carbon: { label: "Carbon", description: "Blue accent — minimal and enterprise." },
} as const

export type ThemeId = keyof typeof THEME_CONFIG

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
