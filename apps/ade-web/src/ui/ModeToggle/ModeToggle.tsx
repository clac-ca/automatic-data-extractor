import clsx from "clsx";

import { useTheme } from "@shared/theme";
import { MoonIcon, SunIcon, SystemIcon } from "@ui/Icons";

type ModeValue = "system" | "light" | "dark";

const MODES: Array<{
  value: ModeValue;
  label: string;
  icon: (props: { className?: string }) => JSX.Element;
}> = [
  { value: "system", label: "System", icon: SystemIcon },
  { value: "light", label: "Light", icon: SunIcon },
  { value: "dark", label: "Dark", icon: MoonIcon },
];

export function ModeToggle({ className }: { readonly className?: string }) {
  const { modePreference, setModePreference } = useTheme();

  return (
    <div
      className={clsx(
        "inline-flex items-center gap-1 rounded-xl border border-border/80 bg-card p-1 shadow-sm",
        className,
      )}
      role="radiogroup"
      aria-label="Color mode"
    >
      {MODES.map((mode) => {
        const isSelected = modePreference === mode.value;
        const Icon = mode.icon;
        return (
          <button
            key={mode.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            aria-label={mode.label}
            title={mode.label}
            onClick={() => setModePreference(mode.value)}
            className={clsx(
              "focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition",
              "hover:bg-muted hover:text-foreground",
              isSelected && "bg-muted text-foreground shadow-sm",
            )}
          >
            <Icon className="h-4 w-4" />
          </button>
        );
      })}
    </div>
  );
}
