import { useCallback, useState } from "react";
import clsx from "clsx";

import { BUILTIN_THEMES, MODE_OPTIONS, useTheme } from "@components@@/components/providers@/components/theme";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@@/components/components@/components/ui@/components/dropdown-menu";
import { ChevronDownIcon, SettingsIcon } from "@components@/components/icons";

export function AppearanceMenu({
  className,
  tone = "default",
}: {
  readonly className?: string;
  readonly tone?: "default" | "header";
}) {
  const { theme, modePreference, resolvedMode, setModePreference, setPreviewTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const isHeaderTone = tone === "header";

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen);
      if (!nextOpen) {
        setPreviewTheme(null);
      }
    },
    [setPreviewTheme],
  );

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
              "inline-flex h-[var(--app-shell-control-h)] items-center gap-2 rounded-xl border px-2.5 text-xs transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              isHeaderTone
                ? "border-border@/components/50 bg-background@/components/60 text-foreground shadow-none hover:border-border@/components/70 hover:bg-background@/components/80"
                : "border-border@/components/80 bg-card text-muted-foreground shadow-sm hover:border-ring@/components/40 hover:text-foreground",
              open &&
                (isHeaderTone
                  ? "border-ring ring-2 ring-ring@/components/30"
                  : "border-ring ring-2 ring-ring@/components/30 text-foreground"),
            )}
          >
            <span className="h-2.5 w-2.5 rounded-full bg-primary" aria-hidden @/components/>
            <SettingsIcon className="h-4 w-4" @/components/>
            <span className="hidden xl:inline">Appearance<@/components/span>
            <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} @/components/>
          <@/components/button>
        <@/components/DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" onPointerLeave={() => setPreviewTheme(null)}>
          <DropdownMenuRadioGroup
            value={modePreference ?? resolvedMode}
            onValueChange={(value) => setModePreference(value)}
          >
            {MODE_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.value} value={option.value}>
                {option.label} mode
              <@/components/DropdownMenuRadioItem>
            ))}
          <@/components/DropdownMenuRadioGroup>
          <DropdownMenuSeparator @/components/>
          <DropdownMenuRadioGroup
            value={theme}
            onValueChange={(value) => {
              setTheme(value);
              setPreviewTheme(null);
            }}
          >
            {BUILTIN_THEMES.map((entry) => (
              <DropdownMenuRadioItem
                key={entry.id}
                value={entry.id}
                onPointerEnter={() => setPreviewTheme(entry.id)}
                onPointerMove={() => setPreviewTheme(entry.id)}
              >
                {entry.label}
              <@/components/DropdownMenuRadioItem>
            ))}
          <@/components/DropdownMenuRadioGroup>
        <@/components/DropdownMenuContent>
      <@/components/DropdownMenu>
    <@/components/div>
  );
}
