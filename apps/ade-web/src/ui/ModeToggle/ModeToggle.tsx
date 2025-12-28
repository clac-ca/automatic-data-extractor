import clsx from "clsx";

import { useTheme } from "@shared/theme";

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

function SunIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="10" cy="10" r="3.5" />
      <path d="M10 2.5v2.2" strokeLinecap="round" />
      <path d="M10 15.3v2.2" strokeLinecap="round" />
      <path d="M2.5 10h2.2" strokeLinecap="round" />
      <path d="M15.3 10h2.2" strokeLinecap="round" />
      <path d="M4.3 4.3l1.6 1.6" strokeLinecap="round" />
      <path d="M14.1 14.1l1.6 1.6" strokeLinecap="round" />
      <path d="M15.7 4.3l-1.6 1.6" strokeLinecap="round" />
      <path d="M5.9 14.1l-1.6 1.6" strokeLinecap="round" />
    </svg>
  );
}

function MoonIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path
        d="M13.8 12.7A5.8 5.8 0 1 1 7.3 3.2a6.7 6.7 0 0 0 6.5 9.5Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SystemIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="3" y="4" width="14" height="9" rx="2" />
      <path d="M7 16h6" strokeLinecap="round" />
      <path d="M10 13v3" strokeLinecap="round" />
    </svg>
  );
}
