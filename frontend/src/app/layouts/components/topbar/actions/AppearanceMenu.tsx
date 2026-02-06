import { useCallback, useMemo, useState, type ReactNode } from "react";
import clsx from "clsx";

import { BUILTIN_THEMES, MODE_OPTIONS, useTheme } from "@/providers/theme";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CheckIcon, ChevronDownIcon, SettingsIcon } from "@/components/icons";

export function AppearanceMenu({
  className,
  tone = "default",
}: {
  readonly className?: string;
  readonly tone?: "default" | "header";
}) {
  const { theme, modePreference, setModePreference, setPreviewTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const isHeaderTone = tone === "header";

  type AppearanceItem = {
    id: string;
    label: string;
    onSelect: () => void;
    onHover?: () => void;
    icon: ReactNode;
  };

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen);
      if (!nextOpen) {
        setPreviewTheme(null);
      }
    },
    [setPreviewTheme],
  );

  const items = useMemo<AppearanceItem[]>(() => {
    const modeItems: AppearanceItem[] = MODE_OPTIONS.map((option) => ({
      id: `mode-${option.value}`,
      label: `${option.label} mode`,
      onSelect: () => {
        setModePreference(option.value);
      },
      icon: modePreference === option.value ? <CheckIcon className="h-4 w-4 text-foreground" /> : null,
    }));

    const themeItems: AppearanceItem[] = BUILTIN_THEMES.map((entry) => ({
      id: `theme-${entry.id}`,
      label: entry.label,
      onSelect: () => {
        setTheme(entry.id);
      },
      onHover: () => setPreviewTheme(entry.id),
      icon: theme === entry.id ? <CheckIcon className="h-4 w-4 text-foreground" /> : null,
    }));

    return [...modeItems, ...themeItems];
  }, [modePreference, setModePreference, setPreviewTheme, setTheme, theme]);

  return (
    <div className={clsx("relative", className)}>
      <DropdownMenu open={open} onOpenChange={handleOpenChange}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="Appearance settings"
            title="Appearance"
            className={clsx(
              "inline-flex h-9 items-center gap-2 rounded-xl border px-2.5 text-xs transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              isHeaderTone
                ? "border-border/50 bg-background/60 text-foreground shadow-none hover:border-border/70 hover:bg-accent hover:text-accent-foreground"
                : "border-border/80 bg-card text-muted-foreground shadow-sm hover:border-ring/40 hover:text-foreground",
              open &&
                (isHeaderTone
                  ? "border-ring bg-accent text-accent-foreground ring-2 ring-ring/30"
                  : "border-ring ring-2 ring-ring/30 text-foreground"),
            )}
          >
            <span className="h-2.5 w-2.5 rounded-full bg-primary" aria-hidden />
            <SettingsIcon className="h-4 w-4" />
            <span className="hidden xl:inline">Appearance</span>
            <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          className="w-64"
          onPointerLeave={() => setPreviewTheme(null)}
        >
          <DropdownMenuLabel className="text-xs uppercase tracking-wide text-muted-foreground">
            Mode
          </DropdownMenuLabel>
          <DropdownMenuGroup>
            {items
              .filter((item) => item.id.startsWith("mode-"))
              .map((item) => (
                <DropdownMenuItem key={item.id} onSelect={item.onSelect} className="gap-3">
                  <span className="flex h-4 w-4 items-center justify-center">{item.icon}</span>
                  <span className="flex-1">{item.label}</span>
                </DropdownMenuItem>
              ))}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-xs uppercase tracking-wide text-muted-foreground">
            Theme
          </DropdownMenuLabel>
          <DropdownMenuGroup>
            {items
              .filter((item) => item.id.startsWith("theme-"))
              .map((item) => (
                <DropdownMenuItem
                  key={item.id}
                  onSelect={item.onSelect}
                  onPointerMove={item.onHover}
                  onFocus={item.onHover}
                  className="gap-3"
                >
                  <span className="flex h-4 w-4 items-center justify-center">{item.icon}</span>
                  <span className="flex-1">{item.label}</span>
                </DropdownMenuItem>
              ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
