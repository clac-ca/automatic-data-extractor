import clsx from "clsx";
import { type ReactNode } from "react";

import { NavLink } from "@app/navigation/Link";
import type { WorkspaceSettingsNavGroup, WorkspaceSettingsRouteId } from "../settingsNav";

interface SettingsLayoutProps {
  readonly workspaceName: string;
  readonly navGroups: readonly WorkspaceSettingsNavGroup[];
  readonly activeSectionId: WorkspaceSettingsRouteId;
  readonly activeSectionLabel: string;
  readonly activeSectionDescription?: string;
  readonly children: ReactNode;
}

export function SettingsLayout({
  workspaceName,
  navGroups,
  activeSectionId,
  activeSectionLabel,
  activeSectionDescription,
  children,
}: SettingsLayoutProps) {
  const flatNav = navGroups.flatMap((group) => group.items);
  const activeTone = flatNav.find((item) => item.id === activeSectionId)?.tone ?? "default";

  return (
    <div className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col px-6 py-6">
      <div className="grid min-h-0 gap-8 lg:grid-cols-[240px,1fr]">
        <nav className="space-y-5" aria-label="Workspace settings sections">
          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="space-y-1">
              <p className="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                Settings
              </p>
              <h1 className="text-lg font-semibold text-foreground">{workspaceName}</h1>
              <p className="text-xs text-muted-foreground">Workspace preferences and access.</p>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="space-y-5">
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
                              active: "bg-danger-50 text-danger-700",
                              idle: "text-danger-600 hover:bg-danger-50/60",
                            }
                          : {
                              active: "bg-accent text-foreground",
                              idle: "text-foreground hover:bg-muted/40",
                            };

                      const baseClasses = clsx(
                        "group flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                        isActive ? toneClasses.active : toneClasses.idle,
                        item.disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
                      );

                      if (item.disabled) {
                        return (
                          <li key={item.id} className="w-full">
                            <div className={baseClasses} aria-disabled>
                              <div className="flex min-w-0 flex-col gap-1">
                                <span className="font-semibold">{item.label}</span>
                                <span className="text-xs text-muted-foreground">{item.description}</span>
                              </div>
                            </div>
                          </li>
                        );
                      }

                      return (
                        <li key={item.id} className="w-full">
                          <NavLink to={item.href} className={baseClasses}>
                            <div className="flex min-w-0 flex-col gap-1">
                              <span className="font-semibold">{item.label}</span>
                              <span className="text-xs text-muted-foreground">{item.description}</span>
                            </div>
                            <span
                              aria-hidden
                              className={clsx(
                                "ml-auto mt-1 h-2 w-2 rounded-full",
                                isActive
                                  ? item.tone === "danger"
                                    ? "bg-danger-500"
                                    : "bg-brand-500"
                                  : "bg-transparent",
                              )}
                            />
                          </NavLink>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </nav>

        <section
          className={clsx(
            "min-h-0 space-y-6",
            activeTone === "danger" && "rounded-2xl border border-danger-200 bg-danger-50/20 p-4",
          )}
        >
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
              Section
            </p>
            <h2 className="text-xl font-semibold text-foreground">{activeSectionLabel}</h2>
            {activeSectionDescription ? (
              <p className="text-sm text-muted-foreground">{activeSectionDescription}</p>
            ) : null}
          </div>
          {children}
        </section>
      </div>
    </div>
  );
}
