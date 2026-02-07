import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import { Laptop, Moon, Palette, Sun } from "lucide-react";

import { useSession } from "@/providers/auth/SessionContext";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { BUILTIN_THEMES, MODE_OPTIONS, WORKSPACE_THEME_MODE_ANCHOR, useTheme } from "@/providers/theme";
import { MOTION_PROFILE } from "@/providers/theme/modeTransition";
import { openReleaseNotes } from "@/config/release-notes";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSystemVersions } from "@/hooks/system";
import { CheckIcon, ChevronDownIcon } from "@/components/icons";
import { getInitials } from "@/lib/format";

const WEB_VERSION_FALLBACK =
  (typeof import.meta.env.VITE_APP_VERSION === "string" ? import.meta.env.VITE_APP_VERSION : "") ||
  (typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "") ||
  "unknown";

export function UnifiedTopbarControls() {
  const session = useSession();
  const navigate = useNavigate();
  const { canAccessOrganizationSettings } = useGlobalPermissions();
  const [versionsOpen, setVersionsOpen] = useState(false);
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <>
      <VersionsDialog open={versionsOpen} onOpenChange={setVersionsOpen} />
      <div className="flex min-w-0 flex-nowrap items-center gap-2">
        <div className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-background/80 p-0.5 shadow-sm backdrop-blur-sm">
          <ModeControl />
          <span className="h-5 w-px bg-border/70" aria-hidden />
          <ThemeMenu />
        </div>
        <ProfileMenu
          displayName={displayName}
          email={email}
          canAccessOrganizationSettings={canAccessOrganizationSettings}
          onOpenOrganizationSettings={() => navigate("/organization/settings")}
          onOpenVersions={() => setVersionsOpen(true)}
        />
      </div>
    </>
  );
}

function ModeControl() {
  const { modePreference, resolvedMode, setModePreference } = useTheme();
  const [open, setOpen] = useState(false);
  const [isPressing, setIsPressing] = useState(false);
  const [iconDrift, setIconDrift] = useState<"to-dark" | "to-light" | null>(null);
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null);
  const applyTimeoutRef = useRef<number | null>(null);
  const pressTimeoutRef = useRef<number | null>(null);
  const isDark = resolvedMode === "dark";

  const clearButtonTimers = () => {
    if (applyTimeoutRef.current !== null) {
      window.clearTimeout(applyTimeoutRef.current);
      applyTimeoutRef.current = null;
    }
    if (pressTimeoutRef.current !== null) {
      window.clearTimeout(pressTimeoutRef.current);
      pressTimeoutRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      if (applyTimeoutRef.current !== null) {
        window.clearTimeout(applyTimeoutRef.current);
      }
      if (pressTimeoutRef.current !== null) {
        window.clearTimeout(pressTimeoutRef.current);
      }
    };
  }, []);

  const resolveOrigin = () => {
    if (!toggleButtonRef.current) {
      return undefined;
    }
    const rect = toggleButtonRef.current.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
  };

  const setAnimatedMode = (next: "light" | "dark" | "system") => {
    setModePreference(next, {
      animate: true,
      origin: resolveOrigin(),
      source: "user",
    });
  };

  const handlePrimaryToggle = () => {
    const next = isDark ? "light" : "dark";
    clearButtonTimers();
    setIsPressing(true);
    setIconDrift(next === "dark" ? "to-dark" : "to-light");

    applyTimeoutRef.current = window.setTimeout(() => {
      setAnimatedMode(next);
      applyTimeoutRef.current = null;
    }, MOTION_PROFILE.buttonPress.leadInMs);

    pressTimeoutRef.current = window.setTimeout(() => {
      setIsPressing(false);
      setIconDrift(null);
      pressTimeoutRef.current = null;
    }, MOTION_PROFILE.buttonPress.durationMs);
  };

  const getModeIcon = (mode: "light" | "dark" | "system") => {
    if (mode === "light") {
      return Sun;
    }
    if (mode === "dark") {
      return Moon;
    }
    return Laptop;
  };

  return (
    <div className="inline-flex items-center">
      <button
        ref={toggleButtonRef}
        type="button"
        data-theme-mode-anchor={WORKSPACE_THEME_MODE_ANCHOR}
        data-pressing={isPressing}
        onClick={handlePrimaryToggle}
        aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        className={clsx(
          "inline-flex h-8 w-8 items-center justify-center rounded-l-full rounded-r-sm text-foreground transition",
          "data-[pressing=true]:animate-[theme-toggle-press_120ms_ease-out]",
          "hover:bg-foreground/10 hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
      >
        <span
          data-mode-icon
          className={clsx(
            "inline-flex items-center justify-center transition-transform duration-150",
            iconDrift === "to-dark" && "rotate-[8deg]",
            iconDrift === "to-light" && "-rotate-[8deg]",
          )}
        >
          <span
            data-mode-icon-drift
            data-drift={iconDrift ?? "idle"}
            className={clsx(
              "inline-flex items-center justify-center",
              "data-[drift=to-dark]:animate-[theme-icon-drift_80ms_ease-out]",
              "data-[drift=to-light]:animate-[theme-icon-drift_80ms_ease-out]",
            )}
          >
            {isDark ? <Sun className="h-[15px] w-[15px]" /> : <Moon className="h-[15px] w-[15px]" />}
          </span>
        </span>
      </button>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="Select color mode"
            className={clsx(
              "inline-flex h-8 w-5 items-center justify-center rounded-l-sm rounded-r-full text-foreground/95 transition",
              "hover:bg-foreground/10 hover:text-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              open && "bg-foreground/12 text-foreground",
            )}
          >
            <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
            <span className="sr-only">Color mode options</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          sideOffset={8}
          className="w-56 rounded-xl border-border/70 bg-popover/95 p-1.5 shadow-lg backdrop-blur-sm"
        >
          <DropdownMenuLabel className="px-2.5 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/90">
            Color mode
          </DropdownMenuLabel>
          <DropdownMenuGroup>
            {MODE_OPTIONS.map((option) => {
              const ModeIcon = getModeIcon(option.value);
              const isSelected = modePreference === option.value;
              return (
                <DropdownMenuItem
                  key={option.value}
                  onSelect={() => setAnimatedMode(option.value)}
                  className={clsx(
                    "group gap-3 rounded-lg px-2.5 py-2 transition-colors",
                    isSelected && "bg-accent/70 text-accent-foreground",
                  )}
                >
                  <span
                    className={clsx(
                      "inline-flex h-4 w-4 items-center justify-center text-muted-foreground transition-colors",
                      isSelected && "text-foreground",
                    )}
                  >
                    <ModeIcon className="h-[15px] w-[15px]" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col leading-tight">
                    <span className="text-[0.95rem] font-medium">{option.label}</span>
                    <span className="text-[11px] text-muted-foreground group-focus:text-accent-foreground/85">
                      {option.description}
                    </span>
                  </span>
                  <span className="inline-flex h-4 w-4 items-center justify-center">
                    {isSelected ? <CheckIcon className="h-3.5 w-3.5 text-foreground" /> : null}
                  </span>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function ProfileMenu({
  displayName,
  email,
  canAccessOrganizationSettings,
  onOpenOrganizationSettings,
  onOpenVersions,
}: {
  readonly displayName: string;
  readonly email: string;
  readonly canAccessOrganizationSettings: boolean;
  readonly onOpenOrganizationSettings: () => void;
  readonly onOpenVersions: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const navigate = useNavigate();
  const initials = getInitials(displayName, email);

  const handleSignOut = () => {
    if (isSigningOut) return;
    setIsSigningOut(true);
    navigate("/logout", { replace: true });
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={clsx(
            "inline-flex h-9 w-9 items-center justify-center rounded-full border text-sm font-semibold transition",
            "border-border/60 bg-background/80 text-foreground shadow-sm backdrop-blur-sm hover:border-border/90 hover:bg-accent hover:text-accent-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "border-ring bg-accent text-accent-foreground ring-2 ring-ring/30",
          )}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Open profile menu"
        >
          <Avatar className="h-6 w-6 rounded-full border border-border/70 shadow-sm">
            <AvatarFallback className="rounded-full bg-primary text-[10px] font-semibold uppercase text-primary-foreground">
              {initials}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 p-2">
        <DropdownMenuLabel className="px-2 py-1.5">
          <div className="space-y-0.5">
            <p className="text-sm font-semibold text-foreground">Signed in as</p>
            <p className="truncate text-xs text-muted-foreground">{email}</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          {canAccessOrganizationSettings ? (
            <DropdownMenuItem onSelect={onOpenOrganizationSettings} className="gap-2">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
                O
              </span>
              <span>Organization Settings</span>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem onSelect={() => openReleaseNotes()} className="gap-2">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
              R
            </span>
            <span>Release notes</span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onOpenVersions} className="gap-2">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
              i
            </span>
            <span>About / Versions</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={handleSignOut}
          disabled={isSigningOut}
          variant="destructive"
          className="justify-between"
        >
          <span>Sign out</span>
          {isSigningOut ? <span className="text-xs text-muted-foreground">...</span> : null}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ThemeMenu() {
  const { theme, setPreviewTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setPreviewTheme(null);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Select theme"
          className={clsx(
            "inline-flex h-8 items-center gap-2 rounded-full px-2 text-xs font-semibold text-foreground transition",
            "hover:bg-accent hover:text-accent-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "bg-accent text-accent-foreground",
          )}
        >
          <Palette className="h-[15px] w-[15px] text-current" aria-hidden />
          <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
          <span className="sr-only">Theme</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-56"
        onPointerLeave={() => setPreviewTheme(null)}
      >
        <DropdownMenuLabel className="text-xs uppercase tracking-wide text-muted-foreground">
          Theme
        </DropdownMenuLabel>
        <DropdownMenuGroup>
          {BUILTIN_THEMES.map((entry) => (
            <DropdownMenuItem
              key={entry.id}
              onSelect={() => setTheme(entry.id)}
              onPointerMove={() => setPreviewTheme(entry.id)}
              onFocus={() => setPreviewTheme(entry.id)}
              className="gap-3"
            >
              <span className="flex h-4 w-4 items-center justify-center">
                {theme === entry.id ? <CheckIcon className="h-4 w-4 text-foreground" /> : null}
              </span>
              <span className="flex-1">{entry.label}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function VersionsDialog({
  open,
  onOpenChange,
}: {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}) {
  const versionsQuery = useSystemVersions({ enabled: open });
  const backendVersion = versionsQuery.data?.backend ?? (versionsQuery.isPending ? "Loading..." : "unknown");
  const engineVersion = versionsQuery.data?.engine ?? (versionsQuery.isPending ? "Loading..." : "unknown");
  const webVersion = versionsQuery.data?.web ?? WEB_VERSION_FALLBACK;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Versions</DialogTitle>
          <DialogDescription>Build details for this ADE deployment.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <VersionRow label="web" value={webVersion} hint="Frontend build" />
          <VersionRow label="backend" value={backendVersion} hint="Backend distribution" />
          <VersionRow label="engine" value={engineVersion} hint="Engine runtime" />
        </div>

        {versionsQuery.isError ? (
          <div className="mt-4 space-y-3">
            <Alert tone="warning">Could not load backend versions. Check connectivity and try again.</Alert>
            <Button size="sm" variant="secondary" onClick={() => versionsQuery.refetch()}>
              Retry
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function VersionRow({
  label,
  value,
  hint,
}: {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border/70 bg-muted px-4 py-3">
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </div>
      <code className="rounded bg-foreground px-2.5 py-1 text-xs font-mono text-background shadow-sm">
        {value}
      </code>
    </div>
  );
}
