export type BuiltInTheme = {
  id: string;
  label: string;
  description: string;
  kind: "accent" | "full";
};

export const BUILT_IN_THEMES: BuiltInTheme[] = [
  { id: "default", label: "Default", description: "Slate neutrals + indigo accent.", kind: "accent" },
  { id: "ocean", label: "Ocean", description: "Cyan accent on slate neutrals.", kind: "accent" },
  { id: "forest", label: "Forest", description: "Emerald accent on slate neutrals.", kind: "accent" },
  { id: "sunset", label: "Sunset", description: "Orange accent on slate neutrals.", kind: "accent" },
  { id: "rose", label: "Rose", description: "Rose accent on slate neutrals.", kind: "accent" },
  { id: "grape", label: "Grape", description: "Violet accent on slate neutrals.", kind: "accent" },
  { id: "sand", label: "Sand", description: "Stone neutrals + teal accent.", kind: "full" },
  { id: "carbon", label: "Carbon", description: "Zinc neutrals + blue accent.", kind: "full" },
];
