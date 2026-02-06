export const THEME_IDS = ["default", "blue", "cyan", "emerald", "amber", "coral", "violet", "teal"] as const

export type ThemeId = (typeof THEME_IDS)[number]

type ThemeDefinition = {
  label: string
  description: string
}

const THEME_CONFIG: Record<ThemeId, ThemeDefinition> = {
  default: { label: "Default", description: "ADE red with bold contrast." },
  blue: { label: "Blue", description: "Blue accent — bold and confident." },
  cyan: { label: "Cyan", description: "Cyan accent — crisp and modern." },
  emerald: { label: "Emerald", description: "Emerald accent — calm and grounded." },
  amber: { label: "Amber", description: "Amber accent — warm and energetic." },
  coral: { label: "Coral", description: "Coral accent — bold and expressive." },
  violet: { label: "Violet", description: "Violet accent — premium and creative." },
  teal: { label: "Teal", description: "Teal accent — bright and balanced." },
}

export type BuiltInTheme = {
  id: ThemeId
  label: string
  description: string
}

export const BUILT_IN_THEMES: BuiltInTheme[] = THEME_IDS.map((id) => ({
  id,
  ...THEME_CONFIG[id],
}))

export function isThemeId(value: string): value is ThemeId {
  return (THEME_IDS as readonly string[]).includes(value)
}
