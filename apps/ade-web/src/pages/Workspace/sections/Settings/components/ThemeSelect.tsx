import clsx from "clsx";

import { BUILTIN_THEMES, type ThemeId } from "@/providers/theme";
import { CheckIcon } from "@/components/icons";

interface ThemeSelectProps {
  readonly theme: ThemeId;
  readonly onThemeChange: (value: ThemeId) => void;
  readonly onThemePreview?: (value: ThemeId | null) => void;
  readonly themes?: Array<{ id: ThemeId; label: string; description: string }>;
  readonly className?: string;
  readonly label?: string;
}

export function ThemeSelect({
  theme,
  onThemeChange,
  onThemePreview,
  themes = BUILTIN_THEMES,
  className,
  label = "Theme",
}: ThemeSelectProps) {
  return (
    <div className={clsx("space-y-2", className)}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <div role="radiogroup" aria-label={label} className="grid gap-2">
        {themes.map((option) => {
          const isSelected = option.id === theme;
          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              data-menu-item
              onClick={() => onThemeChange(option.id)}
              onMouseEnter={() => onThemePreview?.(option.id)}
              onMouseLeave={() => onThemePreview?.(null)}
              onFocus={() => onThemePreview?.(option.id)}
              onBlur={() => onThemePreview?.(null)}
              className={clsx(
                "flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm font-medium transition",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                isSelected
                  ? "border-ring bg-muted text-foreground shadow-sm"
                  : "border-border bg-card text-foreground hover:border-ring/40 hover:bg-muted",
              )}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-sm font-semibold">{option.label}</span>
                <span className="truncate text-xs text-muted-foreground">{option.description}</span>
              </span>
              {isSelected ? <CheckIcon className="h-4 w-4 text-foreground" /> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
