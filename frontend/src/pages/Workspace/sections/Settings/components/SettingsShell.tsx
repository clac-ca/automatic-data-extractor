import clsx from "clsx";
import type { ReactNode } from "react";

import { Link } from "react-router-dom";
import { Separator } from "@/components/ui/separator";
import type { WorkspaceSettingsNavGroup, WorkspaceSettingsRouteId } from "../settingsNav";

interface SettingsShellProps {
  readonly workspaceName: string;
  readonly navGroups: readonly WorkspaceSettingsNavGroup[];
  readonly activeSectionId: WorkspaceSettingsRouteId;
  readonly activeSectionLabel: string;
  readonly activeSectionDescription?: string;
  readonly children: ReactNode;
}

export function SettingsShell({
  workspaceName,
  navGroups,
  activeSectionId,
  activeSectionLabel,
  activeSectionDescription,
  children,
}: SettingsShellProps) {
  const flatNav = navGroups.flatMap((group) => group.items);
  const activeTone = flatNav.find((item) => item.id === activeSectionId)?.tone ?? "default";

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-8">
      <div className="settings-shell-grid grid gap-8 lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start">
        <aside className="w-full lg:sticky lg:top-6 lg:w-64 lg:shrink-0">
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
              Settings
            </p>
            <h1 className="text-lg font-semibold text-foreground">{workspaceName}</h1>
            <p className="text-xs text-muted-foreground">Workspace preferences and access.</p>
          </div>

          <nav className="space-y-6" aria-label="Workspace settings sections">
            {navGroups.map((group) => (
              <div key={group.id} className="space-y-2">
                <p className="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                  {group.label}
                </p>
                <ul className="space-y-1">
                  {group.items.map((item) => {
                    const isActive = item.id === activeSectionId;
                    const toneClasses =
                      item.tone === "danger"
                        ? {
                            active: "bg-destructive/10 text-destructive dark:bg-destructive/20",
                            idle: "text-destructive hover:bg-destructive/10 dark:hover:bg-destructive/20",
                          }
                        : {
                            active: "bg-accent text-foreground",
                            idle: "text-foreground hover:bg-muted/40",
                          };

                    const baseClasses = clsx(
                      "group flex w-full items-start gap-3 rounded-md px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                      isActive ? toneClasses.active : toneClasses.idle,
                      item.disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
                    );

                    if (item.disabled) {
                      return (
                        <li key={item.id} className="w-full">
                          <div className={baseClasses} aria-disabled>
                            <div className="flex min-w-0 flex-col">
                              <span className="font-semibold">{item.label}</span>
                            </div>
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
                        >
                          <div className="flex min-w-0 flex-col">
                            <span className="font-semibold">{item.label}</span>
                          </div>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <main className="min-w-0">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-foreground">{activeSectionLabel}</h2>
            {activeSectionDescription ? (
              <p className="mt-1 text-sm text-muted-foreground">{activeSectionDescription}</p>
            ) : null}
            <Separator className={clsx("mt-4", activeTone === "danger" && "bg-destructive/40")} />
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
