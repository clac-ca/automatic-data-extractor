import clsx from "clsx";

import { THEME_OPTIONS, type ThemePreference } from "@shared/theme";

interface ThemeSelectProps {
  readonly value: ThemePreference;
  readonly onChange: (value: ThemePreference) => void;
  readonly className?: string;
  readonly label?: string;
}

export function ThemeSelect({ value, onChange, className, label = "Appearance" }: ThemeSelectProps) {
  return (
    <div className={clsx("space-y-2", className)}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <div role="radiogroup" aria-label={label} className="grid gap-2">
        {THEME_OPTIONS.map((option) => {
          const isSelected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={isSelected}
              data-menu-item
              onClick={() => onChange(option.value)}
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
