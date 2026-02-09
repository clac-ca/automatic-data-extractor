import clsx from "clsx";
import { Check, ChevronsUpDown, Settings2 } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { OrganizationSettingsNavGroup, OrganizationSettingsRouteId } from "../settingsNav";

interface OrganizationSettingsShellProps {
  readonly navGroups: readonly OrganizationSettingsNavGroup[];
  readonly activeSectionId: OrganizationSettingsRouteId;
  readonly activeSectionLabel: string;
  readonly activeSectionDescription?: string;
  readonly children: ReactNode;
}

export function OrganizationSettingsShell({
  navGroups,
  activeSectionId,
  activeSectionLabel,
  activeSectionDescription,
  children,
}: OrganizationSettingsShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const activeNavItem = useMemo(
    () => navGroups.flatMap((group) => group.items).find((item) => item.id === activeSectionId),
    [activeSectionId, navGroups],
  );

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-8">
      <div className="sticky top-14 z-20 -mx-4 mb-6 border-y border-border/70 bg-background/95 px-4 py-3 backdrop-blur lg:hidden">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.25em] text-muted-foreground">
          Organization settings
        </p>
        <div className="mt-2 flex items-center gap-2">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button type="button" variant="outline" className="w-full justify-between">
                <span className="flex items-center gap-2 truncate">
                  {activeNavItem ? <activeNavItem.icon className="h-4 w-4 text-muted-foreground" /> : <Settings2 className="h-4 w-4 text-muted-foreground" />}
                  <span className="truncate font-semibold">{activeNavItem?.shortLabel ?? activeSectionLabel}</span>
                </span>
                <ChevronsUpDown className="h-4 w-4 text-muted-foreground" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[88vw] max-w-sm p-0 sm:max-w-sm">
              <div className="flex h-full flex-col bg-card">
                <SheetHeader className="border-b border-border/80 px-4 py-4 text-left">
                  <SheetTitle>Organization Settings</SheetTitle>
                  <SheetDescription>Choose a section to manage users, access, and system controls.</SheetDescription>
                </SheetHeader>
                <div className="flex-1 overflow-y-auto px-4 py-4">
                  <OrganizationSettingsNavList
                    navGroups={navGroups}
                    activeSectionId={activeSectionId}
                    onSelect={() => setMobileNavOpen(false)}
                  />
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start lg:gap-8">
        <aside className="hidden w-full lg:sticky lg:top-6 lg:block lg:w-64 lg:shrink-0">
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
              Settings
            </p>
            <h1 className="text-lg font-semibold text-foreground">Organization</h1>
            <p className="text-xs text-muted-foreground">Tenant administration and governance.</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-3 py-3 shadow-xs">
            <OrganizationSettingsNavList navGroups={navGroups} activeSectionId={activeSectionId} />
          </div>
        </aside>

        <main className="min-w-0 animate-in fade-in-0 duration-200">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-foreground">{activeSectionLabel}</h2>
            {activeSectionDescription ? (
              <p className="mt-1 text-sm text-muted-foreground">{activeSectionDescription}</p>
            ) : null}
            <Separator className="mt-4" />
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

function OrganizationSettingsNavList({
  navGroups,
  activeSectionId,
  onSelect,
}: {
  readonly navGroups: readonly OrganizationSettingsNavGroup[];
  readonly activeSectionId: OrganizationSettingsRouteId;
  readonly onSelect?: () => void;
}) {
  return (
    <nav className="space-y-6" aria-label="Organization settings sections">
      {navGroups.map((group) => (
        <div key={group.id} className="space-y-2">
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            {group.label}
          </p>
          <ul className="space-y-1">
            {group.items.map((item) => {
              const isActive = item.id === activeSectionId;
              const baseClasses = clsx(
                "group flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isActive
                  ? "bg-accent text-foreground shadow-xs ring-1 ring-border/70"
                  : "text-foreground hover:bg-muted/40",
                item.disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
              );

              if (item.disabled) {
                return (
                  <li key={item.id} className="w-full">
                    <div className={baseClasses} aria-disabled>
                      <item.icon className="h-4 w-4 text-muted-foreground" />
                      <span className="flex-1 font-semibold">{item.label}</span>
                    </div>
                  </li>
                );
              }

              return (
                <li key={item.id} className="w-full">
                  <Link
                    to={item.href}
                    className={baseClasses}
                    aria-current={isActive ? "page" : undefined}
                    onClick={onSelect}
                  >
                    <item.icon className="h-4 w-4 text-muted-foreground" />
                    <span className="flex-1 font-semibold">{item.label}</span>
                    {isActive ? <Check className="h-4 w-4 text-foreground/70" /> : null}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
