import { useMemo, useState } from "react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import { Palette } from "lucide-react";

import { useSession } from "@/providers/auth/SessionContext";
import { BUILTIN_THEMES, useTheme } from "@/providers/theme";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";
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
        <div className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-background/80 p-0.5 shadow-sm backdrop-blur-sm">
          <AnimatedThemeToggler
            duration={800}
            type="button"
            className={clsx(
              "inline-flex h-8 w-8 items-center justify-center rounded-full text-foreground transition",
              "hover:bg-background/80",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              "[&>svg]:h-4 [&>svg]:w-4",
            )}
            aria-label="Toggle color mode"
          />
          <span className="h-5 w-px bg-border/70" aria-hidden />
          <WorkspaceThemeMenu />
        </div>
        <WorkspaceProfileMenu
          displayName={displayName}
          email={email}
          onOpenVersions={() => setVersionsOpen(true)}
        />
      </div>
    </>
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
            "inline-flex h-9 w-9 items-center justify-center rounded-full border text-sm font-semibold transition",
            "border-border/60 bg-background/80 text-foreground shadow-sm backdrop-blur-sm hover:border-border/90 hover:bg-background",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "border-ring ring-2 ring-ring/30",
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

function WorkspaceThemeMenu() {
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
            "hover:bg-background/80",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "bg-background/90",
          )}
        >
              <Palette className="h-4 w-4 text-foreground" aria-hidden />
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
