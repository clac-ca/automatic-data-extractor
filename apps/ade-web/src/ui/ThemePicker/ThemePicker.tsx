import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

import { BUILTIN_THEMES, useTheme } from "@shared/theme";
import { ContextMenu } from "@ui/ContextMenu";

const MENU_OFFSET = 6;

export function ThemePicker({ className }: { readonly className?: string }) {
  const { theme, setTheme, resolvedMode, setPreviewTheme } = useTheme();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);

  const currentTheme = useMemo(() => BUILTIN_THEMES.find((entry) => entry.id === theme), [theme]);
  const themeLabel = currentTheme?.label ?? theme;

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) {
      return;
    }
    const rect = triggerRef.current.getBoundingClientRect();
    setPosition({ x: rect.left, y: rect.bottom + MENU_OFFSET });
  }, []);

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
  }, [open, updatePosition]);

  const items = useMemo(
    () =>
      BUILTIN_THEMES.map((entry) => ({
        id: entry.id,
        label: entry.label,
        onSelect: () => {
          setTheme(entry.id);
          setPreviewTheme(null);
          setOpen(false);
        },
        onHover: () => setPreviewTheme(entry.id),
        icon: entry.id === theme ? <CheckIcon /> : undefined,
      })),
    [setPreviewTheme, setTheme, theme],
  );

  return (
    <div className={clsx("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Theme: ${themeLabel}`}
        title={`Theme: ${themeLabel}`}
        className={clsx(
          "focus-ring inline-flex h-9 items-center gap-2 rounded-xl border border-border/80 bg-card px-2.5 text-xs",
          "text-muted-foreground shadow-sm transition hover:border-border-strong hover:text-foreground",
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
        <span className="hidden md:inline">Theme</span>
        <ChevronIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
      </button>

      <ContextMenu
        open={open}
        position={position}
        onClose={() => {
          setOpen(false);
          setPreviewTheme(null);
        }}
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

function ChevronIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
