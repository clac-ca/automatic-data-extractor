import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

import { BUILTIN_THEMES, MODE_OPTIONS, useTheme } from "@components/providers/theme";
import { ContextMenu } from "@/components/ui/context-menu";
import { CheckIcon, ChevronDownIcon, SettingsIcon } from "@components/icons";

const MENU_OFFSET = 8;

export function AppearanceMenu({
  className,
  tone = "default",
}: {
  readonly className?: string;
  readonly tone?: "default" | "header";
}) {
  const { theme, modePreference, resolvedMode, setModePreference, setPreviewTheme, setTheme } = useTheme();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const isHeaderTone = tone === "header";

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) {
      return;
    }
    const rect = triggerRef.current.getBoundingClientRect();
    setPosition({ x: rect.left, y: rect.bottom + MENU_OFFSET });
  }, []);

  const closeMenu = useCallback(() => {
    setOpen(false);
    setPreviewTheme(null);
  }, [setPreviewTheme]);

  useEffect(() => {
    if (!open) {
      setPreviewTheme(null);
      return;
    }
    updatePosition();
    const handleResize = () => updatePosition();
    window.addEventListener("resize", handleResize);
    window.addEventListener("scroll", handleResize, true);
    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("scroll", handleResize, true);
    };
  }, [open, setPreviewTheme, updatePosition]);

  const items = useMemo(() => {
    const modeItems = MODE_OPTIONS.map((option) => ({
      id: `mode-${option.value}`,
      label: `${option.label} mode`,
      onSelect: () => {
        setModePreference(option.value);
        closeMenu();
      },
      icon: modePreference === option.value ? <CheckIcon className="h-3.5 w-3.5 text-foreground" /> : undefined,
    }));

    const themeItems = BUILTIN_THEMES.map((entry, index) => ({
      id: `theme-${entry.id}`,
      label: entry.label,
      onSelect: () => {
        setTheme(entry.id);
        closeMenu();
      },
      onHover: () => setPreviewTheme(entry.id),
      icon: theme === entry.id ? <CheckIcon className="h-3.5 w-3.5 text-foreground" /> : undefined,
      dividerAbove: index === 0,
    }));

    return [...modeItems, ...themeItems];
  }, [closeMenu, modePreference, setModePreference, setPreviewTheme, setTheme, theme]);

  return (
    <div className={clsx("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Appearance settings"
        title="Appearance"
        className={clsx(
          "inline-flex h-9 items-center gap-2 rounded-xl border px-2.5 text-xs transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          isHeaderTone
            ? "border-border/50 bg-background/60 text-foreground shadow-none hover:border-border/70 hover:bg-background/80"
            : "border-border/80 bg-card text-muted-foreground shadow-sm hover:border-ring/40 hover:text-foreground",
          open &&
            (isHeaderTone
              ? "border-ring ring-2 ring-ring/30"
              : "border-ring ring-2 ring-ring/30 text-foreground"),
        )}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span className="h-2.5 w-2.5 rounded-full bg-primary" aria-hidden />
        <SettingsIcon className="h-4 w-4" />
        <span className="hidden xl:inline">Appearance</span>
        <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
      </button>

      <ContextMenu
        open={open}
        position={position}
        onClose={closeMenu}
        items={items}
        appearance={resolvedMode}
        onPointerLeave={() => setPreviewTheme(null)}
      />
    </div>
  );
}
