export const THEME_IDS = [
  "default",
  "ocean",
  "forest",
  "sunset",
  "rose",
  "grape",
  "sand",
  "carbon",
] as const

export type ThemeId = (typeof THEME_IDS)[number]

export type BuiltInTheme = {
  id: ThemeId
  label: string
  description: string
}

export const BUILT_IN_THEMES: BuiltInTheme[] = [
  { id: "default", label: "Default", description: "Indigo accent on clean neutrals." },
  { id: "ocean", label: "Ocean", description: "Cyan/teal accent — crisp and modern." },
  { id: "forest", label: "Forest", description: "Emerald accent — calm and grounded." },
  { id: "sunset", label: "Sunset", description: "Orange accent — warm and energetic." },
  { id: "rose", label: "Rose", description: "Rose accent — bold and expressive." },
  { id: "grape", label: "Grape", description: "Violet accent — premium and creative." },
  { id: "sand", label: "Sand", description: "Teal accent on warm neutrals." },
  { id: "carbon", label: "Carbon", description: "Blue accent — minimal and enterprise." },
]

export function isThemeId(value: string): value is ThemeId {
  return (THEME_IDS as readonly string[]).includes(value)
}
