import clsx from "clsx";

import { MODE_OPTIONS, useTheme } from "@components/providers/theme";
import { ThemeSelect } from "@components/ui/theme-select";
import { CheckIcon } from "@components/icons";
import { SettingsPanel } from "../components/SettingsPanel";


export function AppearanceSettingsPage() {
  const { modePreference, setModePreference, theme, setTheme } = useTheme();

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <SettingsPanel
          title="Color mode"
          description="Use the system setting or set a fixed light or dark mode."
        >
          <div role="radiogroup" aria-label="Color mode" className="grid gap-2">
            {MODE_OPTIONS.map((option) => {
              const isSelected = option.value === modePreference;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => setModePreference(option.value)}
                  className={clsx(
                    "flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm font-medium transition",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                    isSelected
                      ? "border-brand-400 bg-muted text-foreground shadow-sm"
                      : "border-border bg-card text-foreground hover:border-border-strong hover:bg-muted",
                  )}
                >
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-sm font-semibold">{option.label}</span>
                    <span className="truncate text-xs text-muted-foreground">{option.description}</span>
                  </span>
                  {isSelected ? <CheckIcon className="h-4 w-4 text-brand-500" /> : null}
                </button>
              );
            })}
          </div>
        </SettingsPanel>

        <SettingsPanel title="Theme" description="Pick the base color palette for this workspace.">
          <ThemeSelect theme={theme} onThemeChange={setTheme} label="Theme" />
        </SettingsPanel>
      </div>
    </div>
  );
}
