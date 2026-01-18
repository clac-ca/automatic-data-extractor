import { useCallback, useMemo, useState, type ReactNode } from "react";
import clsx from "clsx";

import { useNavigate } from "react-router-dom";
import { ChevronDownIcon, SpinnerIcon } from "@/components/icons";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ProfileDropdownAction {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly onSelect: () => void;
}

interface ProfileDropdownProps {
  readonly displayName: string;
  readonly email: string;
  readonly actions?: readonly ProfileDropdownAction[];
  readonly tone?: "default" | "header";
}

export function ProfileDropdown({ displayName, email, actions = [], tone = "default" }: ProfileDropdownProps) {
  const [open, setOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const navigate = useNavigate();
  const initials = useMemo(() => deriveInitials(displayName || email), [displayName, email]);
  const isHeaderTone = tone === "header";
  const avatarSizeClass = "h-8 w-8";
  const actionIconSizeClass = "h-7 w-7";

  const handleMenuAction = useCallback((action: () => void) => {
    action();
  }, []);

  const handleSignOut = useCallback(async () => {
    if (isSigningOut) return;
    setIsSigningOut(true);
    navigate("/logout", { replace: true });
  }, [isSigningOut, navigate]);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={clsx(
            "inline-flex items-center rounded-xl border text-left text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            isHeaderTone ? "h-9 gap-2 px-2.5" : "gap-3 px-2.5 py-1.5",
            isHeaderTone
              ? "border-border/50 bg-background/60 text-foreground shadow-none hover:border-border/70 hover:bg-background/80"
              : "border-border bg-card text-muted-foreground shadow-sm hover:border-ring/40 hover:text-foreground",
            open && "border-ring ring-2 ring-ring/30",
          )}
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <Avatar className={clsx("shrink-0 rounded-lg shadow-sm", avatarSizeClass)}>
            <AvatarFallback className="rounded-lg bg-primary text-xs font-semibold uppercase leading-none text-primary-foreground">
              {initials}
            </AvatarFallback>
          </Avatar>
          {isHeaderTone ? (
            <span className="hidden min-w-0 xl:block">
              <span className="truncate text-sm font-semibold text-foreground">{displayName}</span>
            </span>
          ) : (
            <span className="hidden min-w-0 flex-col xl:flex">
              <span className="truncate text-sm font-semibold text-foreground">{displayName}</span>
              <span className="truncate text-xs text-muted-foreground">{email}</span>
            </span>
          )}
          <ChevronDownIcon
            className={clsx(
              "h-4 w-4 transition-transform duration-150 text-muted-foreground",
              open && "rotate-180",
            )}
          />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 p-2">
        <DropdownMenuLabel className="px-2 py-1.5">
          <div className="space-y-0.5">
            <p className="text-sm font-semibold text-foreground">Signed in as</p>
            <p className="truncate text-xs text-muted-foreground">{email}</p>
          </div>
        </DropdownMenuLabel>
        {actions.length > 0 ? <DropdownMenuSeparator /> : null}
        {actions.length > 0 ? (
          <DropdownMenuGroup>
            {actions.map((action) => (
              <DropdownMenuItem
                key={action.id}
                onSelect={() => handleMenuAction(action.onSelect)}
                className="items-start gap-3 rounded-lg px-3 py-2"
              >
                <span
                  className={clsx(
                    "inline-flex items-center justify-center rounded-md bg-muted text-[0.65rem] font-semibold leading-none text-muted-foreground",
                    actionIconSizeClass,
                  )}
                >
                  {action.icon ?? action.label.charAt(0).toUpperCase()}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-sm font-medium">{action.label}</span>
                  {action.description ? (
                    <span className="truncate text-xs text-muted-foreground">{action.description}</span>
                  ) : null}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={handleSignOut}
          disabled={isSigningOut}
          className="justify-between rounded-lg px-3 py-2 font-semibold text-muted-foreground"
        >
          <span>Sign out</span>
          {isSigningOut ? <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
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
