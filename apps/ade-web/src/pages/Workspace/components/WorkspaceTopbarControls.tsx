import { useMemo, useState } from "react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";

import { useSession } from "@/providers/auth/SessionContext";
import {
  BUILTIN_THEMES,
  MODE_OPTIONS,
  useTheme,
  type ModePreference,
} from "@/providers/theme";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSystemVersions } from "@/hooks/system";
import { CheckIcon, ChevronDownIcon, MoonIcon, SunIcon, SystemIcon } from "@/components/icons";

const MODE_ICONS: Record<ModePreference, typeof SunIcon> = {
  system: SystemIcon,
  light: SunIcon,
  dark: MoonIcon,
};

const ADE_WEB_VERSION =
  (typeof import.meta.env.VITE_APP_VERSION === "string" ? import.meta.env.VITE_APP_VERSION : "") ||
  (typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "") ||
  "unknown";

export function WorkspaceTopbarControls() {
  const session = useSession();
  const [versionsOpen, setVersionsOpen] = useState(false);
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <>
      <WorkspaceVersionsDialog open={versionsOpen} onOpenChange={setVersionsOpen} />
      <div className="flex min-w-0 flex-nowrap items-center gap-2">
        <WorkspaceAppearanceMenu />
        <WorkspaceProfileMenu
          displayName={displayName}
          email={email}
          onOpenVersions={() => setVersionsOpen(true)}
        />
      </div>
    </>
  );
}

function WorkspaceAppearanceMenu() {
  const { modePreference, setModePreference, theme, setTheme, setPreviewTheme } = useTheme();
  const [open, setOpen] = useState(false);

  const themeLabel = useMemo(
    () => BUILTIN_THEMES.find((entry) => entry.id === theme)?.label ?? theme,
    [theme],
  );

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setPreviewTheme(null);
    }
  };

  const ModeIcon = MODE_ICONS[modePreference];

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={clsx(
            "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-sm font-semibold transition",
            "border-border/60 bg-background/80 text-foreground shadow-sm backdrop-blur-sm hover:border-border/90 hover:bg-background",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "border-ring ring-2 ring-ring/30",
          )}
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary/10 text-primary">
            <ModeIcon className="h-3.5 w-3.5" />
          </span>
          <span className="hidden lg:inline">Appearance</span>
          <ChevronDownIcon className="h-4 w-4 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-72"
        onPointerLeave={() => setPreviewTheme(null)}
      >
        <DropdownMenuLabel className="text-xs uppercase tracking-wide text-muted-foreground">
          Mode
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={modePreference}
          onValueChange={(value) => setModePreference(value as ModePreference)}
        >
          {MODE_OPTIONS.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value} className="items-start">
              <div className="flex min-w-0 flex-col">
                <span className="text-sm font-medium text-foreground">{option.label}</span>
                <span className="text-xs text-muted-foreground">{option.description}</span>
              </div>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />

        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <span className="flex-1">Theme</span>
            <span className="text-xs text-muted-foreground">{themeLabel}</span>
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="w-72" onPointerLeave={() => setPreviewTheme(null)}>
            <DropdownMenuLabel className="text-xs uppercase tracking-wide text-muted-foreground">
              Themes
            </DropdownMenuLabel>
            <DropdownMenuGroup>
              {BUILTIN_THEMES.map((entry) => {
                const isSelected = entry.id === theme;
                return (
                  <DropdownMenuItem
                    key={entry.id}
                    onSelect={() => setTheme(entry.id)}
                    onPointerMove={() => setPreviewTheme(entry.id)}
                    onFocus={() => setPreviewTheme(entry.id)}
                    className="gap-2"
                  >
                    <div className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-sm font-medium text-foreground">{entry.label}</span>
                      <span className="truncate text-xs text-muted-foreground">{entry.description}</span>
                    </div>
                    {isSelected ? <CheckIcon className="h-4 w-4 text-foreground" /> : null}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function WorkspaceProfileMenu({
  displayName,
  email,
  onOpenVersions,
}: {
  readonly displayName: string;
  readonly email: string;
  readonly onOpenVersions: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const navigate = useNavigate();
  const initials = useMemo(() => deriveInitials(displayName || email), [displayName, email]);

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
            "inline-flex h-9 items-center gap-2 rounded-full border px-2.5 text-sm font-semibold transition",
            "border-border/60 bg-background/80 text-foreground shadow-sm backdrop-blur-sm hover:border-border/90 hover:bg-background",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "border-ring ring-2 ring-ring/30",
          )}
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <Avatar className="h-6 w-6 rounded-full border border-border/70 shadow-sm">
            <AvatarFallback className="rounded-full bg-primary text-[10px] font-semibold uppercase text-primary-foreground">
              {initials}
            </AvatarFallback>
          </Avatar>
          <span className="hidden lg:block max-w-[10rem] truncate text-sm font-semibold">
            {displayName}
          </span>
          <ChevronDownIcon className="h-4 w-4 text-muted-foreground" />
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

function WorkspaceVersionsDialog({
  open,
  onOpenChange,
}: {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}) {
  const versionsQuery = useSystemVersions({ enabled: open });
  const apiVersion = versionsQuery.data?.ade_api ?? (versionsQuery.isPending ? "Loading..." : "unknown");
  const engineVersion = versionsQuery.data?.ade_engine ?? (versionsQuery.isPending ? "Loading..." : "unknown");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Versions</DialogTitle>
          <DialogDescription>Build details for this ADE deployment.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <VersionRow label="ade-web" value={ADE_WEB_VERSION} hint="Frontend build" />
          <VersionRow label="ade-api" value={apiVersion} hint="Backend service" />
          <VersionRow label="ade-engine" value={engineVersion} hint="Engine runtime" />
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

function deriveInitials(source: string) {
  const parts = source
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) return "*";
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}
