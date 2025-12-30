import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

import { BUILTIN_THEMES, MODE_OPTIONS, useTheme } from "@shared/theme";
import { ContextMenu } from "@ui/ContextMenu";

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
      icon: modePreference === option.value ? <CheckIcon /> : undefined,
    }));

    const themeItems = BUILTIN_THEMES.map((entry, index) => ({
      id: `theme-${entry.id}`,
      label: entry.label,
      onSelect: () => {
        setTheme(entry.id);
        closeMenu();
      },
      onHover: () => setPreviewTheme(entry.id),
      icon: theme === entry.id ? <CheckIcon /> : undefined,
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
          "focus-ring inline-flex h-9 items-center gap-2 rounded-xl border px-2.5 text-xs transition",
          isHeaderTone
            ? "border-header-border/40 bg-header/25 text-header-foreground shadow-none hover:border-header-border/70 hover:bg-header/30"
            : "border-border/80 bg-card text-muted-foreground shadow-sm hover:border-border-strong hover:text-foreground",
          open &&
            (isHeaderTone
              ? "border-header-ring ring-2 ring-header-ring/30"
              : "border-brand-400 ring-2 ring-brand-500/10 text-foreground"),
        )}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: "rgb(var(--sys-color-accent))" }}
          aria-hidden
        />
        <AppearanceIcon className="h-4 w-4" />
        <span className="hidden sm:inline">Appearance</span>
        <ChevronIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
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

function CheckIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-brand-500" viewBox="0 0 20 20" fill="none" aria-hidden>
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

function AppearanceIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M3.5 6h13" strokeLinecap="round" />
      <path d="M3.5 14h13" strokeLinecap="round" />
      <circle cx="7" cy="6" r="2" />
      <circle cx="13" cy="14" r="2" />
    </svg>
  );
}

function ChevronIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
