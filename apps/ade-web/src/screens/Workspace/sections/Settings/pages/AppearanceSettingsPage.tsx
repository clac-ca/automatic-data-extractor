import clsx from "clsx";

import { MODE_OPTIONS, useTheme } from "@shared/theme";
import { ThemeSelect } from "@ui/ThemeSelect";

import { SettingsSectionHeader } from "../components/SettingsSectionHeader";

export function AppearanceSettingsPage() {
  const { modePreference, setModePreference, theme, setTheme } = useTheme();

  return (
    <div className="space-y-6">
      <SettingsSectionHeader
        title="Appearance"
        description="Choose your color mode and theme. These preferences follow your account."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-border bg-card p-6 shadow-soft">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-foreground">Color mode</h3>
            <p className="text-sm text-muted-foreground">
              Use the system setting or set a fixed light or dark mode.
            </p>
          </div>
          <div role="radiogroup" aria-label="Color mode" className="mt-4 grid gap-2">
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
        </section>

        <section className="rounded-2xl border border-border bg-card p-6 shadow-soft">
          <ThemeSelect theme={theme} onThemeChange={setTheme} label="Theme" />
        </section>
      </div>
    </div>
  );
}

function CheckIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={clsx("h-4 w-4", className)} viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M5 10.5l3 3 7-7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
