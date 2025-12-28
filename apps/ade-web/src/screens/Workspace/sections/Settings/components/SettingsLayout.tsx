import clsx from "clsx";
import { useMemo, useState, type ReactNode } from "react";

import { NavLink } from "@app/nav/Link";
import type { WorkspaceSettingsNavGroup, WorkspaceSettingsRouteId } from "../settingsNav";
import { Input } from "@ui/Input";

interface SettingsLayoutProps {
  readonly workspaceName: string;
  readonly navGroups: readonly WorkspaceSettingsNavGroup[];
  readonly activeSectionId: WorkspaceSettingsRouteId;
  readonly activeSectionLabel: string;
  readonly activeSectionDescription?: string;
  readonly activeGroupLabel: string;
  readonly children: ReactNode;
}

export function SettingsLayout({
  workspaceName,
  navGroups,
  activeSectionId,
  activeSectionLabel,
  activeSectionDescription,
  activeGroupLabel,
  children,
}: SettingsLayoutProps) {
  const flatNav = navGroups.flatMap((group) => group.items);
  const activeTone = flatNav.find((item) => item.id === activeSectionId)?.tone ?? "default";
  const [navFilter, setNavFilter] = useState("");

  const normalizedFilter = navFilter.trim().toLowerCase();
  const navGroupsFiltered = useMemo(() => {
    if (!normalizedFilter) {
      return navGroups;
    }
    return navGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => {
          const haystack = `${item.label} ${item.description}`.toLowerCase();
          return haystack.includes(normalizedFilter);
        }),
      }))
      .filter((group) => group.items.length > 0);
  }, [navGroups, normalizedFilter]);

  const breadcrumbs = useMemo(
    () => ["Settings", activeGroupLabel, activeSectionLabel].filter(Boolean),
    [activeGroupLabel, activeSectionLabel],
  );

  return (
    <div className="space-y-6">
      <header className="rounded-3xl border border-border bg-card p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
              <span>Workspace</span>
              <span aria-hidden>•</span>
              <span>Settings</span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-foreground">{workspaceName}</h1>
              <span className="inline-flex items-center rounded-full bg-muted px-3 py-1 text-xs font-semibold text-foreground">
                Settings
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {breadcrumbs.map((crumb, index) => (
                <span key={crumb} className="inline-flex items-center gap-2">
                  <span className={index === breadcrumbs.length - 1 ? "font-semibold text-foreground" : "text-muted-foreground"}>
                    {crumb}
                  </span>
                  {index < breadcrumbs.length - 1 ? <span aria-hidden className="text-muted-foreground">/</span> : null}
                </span>
              ))}
            </div>
            {activeSectionDescription ? (
              <p className="max-w-3xl text-sm text-muted-foreground">{activeSectionDescription}</p>
            ) : null}
          </div>
          <div className="w-full max-w-xs">
            <Input
              value={navFilter}
              onChange={(event) => setNavFilter(event.target.value)}
              placeholder="Search settings"
              aria-label="Search workspace settings"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">Filter sections by name or description.</p>
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[280px,1fr]">
        <nav
          className="rounded-2xl border border-border bg-card p-4 shadow-soft"
          aria-label="Workspace settings sections"
        >
          <div className="space-y-4">
            {navGroupsFiltered.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border bg-background p-3 text-xs text-muted-foreground">
                No sections match "{navFilter}".
              </p>
            ) : (
              navGroupsFiltered.map((group) => (
                <div key={group.id} className="space-y-2">
                  <p className="px-1 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                    {group.label}
                  </p>
                  <ul className="space-y-1">
                    {group.items.map((item) => {
                      const isActive = item.id === activeSectionId;
                      const toneClasses =
                        item.tone === "danger"
                          ? {
                              active: "bg-danger-50 text-danger-700 ring-danger-100",
                              idle: "hover:bg-danger-50/60 text-danger-700",
                              badgeActive: "bg-danger-500 text-on-danger",
                              badgeIdle: "bg-danger-100 text-danger-700 group-hover:bg-danger-200",
                            }
                          : {
                              active: "bg-brand-50 text-brand-700 ring-brand-100",
                              idle: "hover:bg-background text-foreground",
                              badgeActive: "bg-brand-500 text-on-brand",
                              badgeIdle: "bg-muted text-muted-foreground group-hover:bg-muted",
                            };

                      const baseClasses = clsx(
                        "group flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2",
                        isActive ? toneClasses.active : toneClasses.idle,
                        item.disabled && "cursor-not-allowed opacity-50 ring-0 hover:bg-card",
                      );

                      if (item.disabled) {
                        return (
                          <li key={item.id} className="w-full">
                            <div className={baseClasses} aria-disabled>
                              <div className="flex min-w-0 flex-col">
                                <span className="text-sm font-semibold">{item.label}</span>
                                <span className="text-xs text-muted-foreground">{item.description}</span>
                              </div>
                            </div>
                          </li>
                        );
                      }

                      return (
                        <li key={item.id} className="w-full">
                          <NavLink to={item.href} className={baseClasses}>
                            <div className="flex min-w-0 flex-col">
                              <span className="text-sm font-semibold">{item.label}</span>
                              <span className="text-xs text-muted-foreground">{item.description}</span>
                            </div>
                            <span
                              aria-hidden
                              className={clsx(
                                "ml-auto inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold transition",
                                isActive ? toneClasses.badgeActive : toneClasses.badgeIdle,
                              )}
                            >
                              {item.label.slice(0, 1).toUpperCase()}
                            </span>
                          </NavLink>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))
            )}
          </div>
        </nav>

        <div
          className={clsx(
            "space-y-6 rounded-3xl border border-border bg-card p-6 shadow-soft",
            activeTone === "danger" && "border-danger-100 bg-danger-50/40",
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
