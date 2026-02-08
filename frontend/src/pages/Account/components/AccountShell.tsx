import clsx from "clsx";
import type { LucideIcon } from "lucide-react";
import { Check, ChevronsUpDown, Menu } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export interface AccountNavItem {
  readonly id: string;
  readonly label: string;
  readonly shortLabel: string;
  readonly description: string;
  readonly href: string;
  readonly icon: LucideIcon;
}

interface AccountShellProps {
  readonly navItems: readonly AccountNavItem[];
  readonly activeSectionId: string;
  readonly heading: string;
  readonly sectionDescription: string;
  readonly displayName: string;
  readonly email: string;
  readonly initials: string;
  readonly children: ReactNode;
}

export function AccountShell({
  navItems,
  activeSectionId,
  heading,
  sectionDescription,
  displayName,
  email,
  initials,
  children,
}: AccountShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const activeNavItem = useMemo(
    () => navItems.find((item) => item.id === activeSectionId),
    [activeSectionId, navItems],
  );

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-8">
      <section className="rounded-2xl border border-border/80 bg-gradient-to-br from-card via-card to-accent/20 p-5 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar className="h-12 w-12 border border-border/70 shadow-sm sm:h-14 sm:w-14">
              <AvatarFallback className="bg-primary text-sm font-semibold uppercase text-primary-foreground sm:text-base">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="text-[0.65rem] font-semibold uppercase tracking-[0.26em] text-muted-foreground">
                Account Center
              </p>
              <h1 className="truncate text-xl font-semibold text-foreground sm:text-2xl">{displayName}</h1>
              <p className="truncate text-sm text-muted-foreground">{email}</p>
            </div>
          </div>
          <div className="rounded-full border border-border/80 bg-background/80 px-3 py-1.5 text-xs text-muted-foreground shadow-xs">
            Secure your profile and personal credentials.
          </div>
        </div>
      </section>

      <div className="sticky top-14 z-20 -mx-4 mt-5 border-y border-border/70 bg-background/95 px-4 py-3 backdrop-blur lg:hidden">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.25em] text-muted-foreground">
          Section
        </p>
        <div className="mt-2">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button type="button" variant="outline" className="w-full justify-between">
                <span className="flex min-w-0 items-center gap-2 truncate">
                  {activeNavItem ? (
                    <activeNavItem.icon className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <Menu className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="truncate font-semibold">{activeNavItem?.shortLabel ?? heading}</span>
                </span>
                <ChevronsUpDown className="h-4 w-4 text-muted-foreground" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[88vw] max-w-sm p-0 sm:max-w-sm">
              <div className="flex h-full flex-col bg-card">
                <SheetHeader className="border-b border-border/80 px-4 py-4 text-left">
                  <SheetTitle>Account Settings</SheetTitle>
                  <SheetDescription>Choose what you want to manage for your profile and security.</SheetDescription>
                </SheetHeader>
                <div className="flex-1 overflow-y-auto px-4 py-4">
                  <AccountNavList
                    navItems={navItems}
                    activeSectionId={activeSectionId}
                    onSelect={() => setMobileNavOpen(false)}
                  />
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start lg:gap-8">
        <aside className="hidden lg:sticky lg:top-6 lg:block">
          <div className="rounded-xl border border-border bg-card px-3 py-3 shadow-xs">
            <AccountNavList navItems={navItems} activeSectionId={activeSectionId} />
          </div>
        </aside>

        <main className="min-w-0 animate-in fade-in-0 duration-200">
          <header className="mb-6 space-y-1">
            <h2 className="text-xl font-semibold text-foreground">{heading}</h2>
            <p className="text-sm text-muted-foreground">{sectionDescription}</p>
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}

function AccountNavList({
  navItems,
  activeSectionId,
  onSelect,
}: {
  readonly navItems: readonly AccountNavItem[];
  readonly activeSectionId: string;
  readonly onSelect?: () => void;
}) {
  return (
    <nav className="space-y-1" aria-label="Account settings sections">
      {navItems.map((item) => {
        const isActive = item.id === activeSectionId;
        return (
          <Link
            key={item.id}
            to={item.href}
            className={clsx(
              "group flex w-full items-start gap-3 rounded-md px-3 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              isActive ? "bg-accent text-accent-foreground ring-1 ring-border/70" : "hover:bg-muted/40",
            )}
            aria-current={isActive ? "page" : undefined}
            onClick={onSelect}
          >
            <item.icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-foreground">{item.label}</span>
              <span className="block text-xs text-muted-foreground">{item.description}</span>
            </span>
            {isActive ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-foreground/80" /> : null}
          </Link>
        );
      })}
    </nav>
  );
}
