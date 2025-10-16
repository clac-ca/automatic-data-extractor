import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { createPortal } from "react-dom";
import clsx from "clsx";

import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import type { WorkspaceSectionDescriptor } from "../../workspaces/sections";
import {
  getWorkspacePrimaryNavItems,
  getWorkspaceSecondaryNavigation,
} from "../../workspaces/navigation";
import type { WorkspaceSecondaryNavigation } from "../../workspaces/navigation";
import { WorkspaceQuickSwitcher } from "../../workspaces/WorkspaceQuickSwitcher";

export interface WorkspaceNavigationDrawerProps {
  readonly open: boolean;
  readonly workspace: WorkspaceProfile;
  readonly workspaces: readonly WorkspaceProfile[];
  readonly section: WorkspaceSectionDescriptor;
  readonly onClose: () => void;
  readonly onNavigate?: () => void;
  readonly onSelectWorkspace: (workspaceId: string) => void;
  readonly onCreateWorkspace?: () => void;
  readonly onManageWorkspace?: () => void;
}

export function WorkspaceNavigationDrawer({
  open,
  workspace,
  workspaces,
  section,
  onClose,
  onNavigate,
  onSelectWorkspace,
  onCreateWorkspace,
  onManageWorkspace,
}: WorkspaceNavigationDrawerProps) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const primaryItems = getWorkspacePrimaryNavItems(workspace);
  const secondaryNavigation = getWorkspaceSecondaryNavigation(workspace.id, section);

  const content = (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        className="h-full flex-1 bg-slate-900/30 backdrop-blur-sm"
        aria-label="Close navigation"
        onClick={onClose}
      />
      <div
        className="relative h-full w-[min(20rem,90vw)] bg-white shadow-2xl ring-1 ring-slate-900/10 transition-transform duration-200 ease-out"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-navigation-drawer-title"
      >
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4">
          <h2 id="workspace-navigation-drawer-title" className="text-sm font-semibold text-slate-900">
            Navigate
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
            aria-label="Close navigation"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="flex flex-col gap-6 overflow-y-auto px-4 py-5">
          <WorkspaceQuickSwitcher
            workspace={workspace}
            workspaces={workspaces}
            onSelectWorkspace={(workspaceId) => {
              onSelectWorkspace(workspaceId);
              onNavigate?.();
            }}
            onCreateWorkspace={onCreateWorkspace}
            onManageWorkspace={onManageWorkspace}
            size="compact"
            tone="ghost"
            variant="default"
            showSlug={false}
          />

          <NavigationGroup title="Workspace" items={primaryItems} onNavigate={onNavigate} />
          <SecondaryNavigationGroup
            title={section.label}
            navigation={secondaryNavigation}
            onNavigate={onNavigate}
          />
        </div>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}

interface NavigationGroupProps {
  readonly title: string;
  readonly items: readonly {
    readonly id: string;
    readonly label: string;
    readonly href: string;
    readonly description?: string;
  }[];
  readonly onNavigate?: () => void;
}

function NavigationGroup({ title, items, onNavigate }: NavigationGroupProps) {
  const anchorId = `${title.toLowerCase().replace(/\s+/g, "-")}-group`;
  return (
    <section aria-labelledby={anchorId} className="space-y-3">
      <div id={anchorId} className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </div>
      <ul className="space-y-1" role="list">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={item.href}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  "flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  isActive ? "bg-slate-100 text-slate-900" : "text-slate-600 hover:bg-slate-100",
                )
              }
            >
              <span className="truncate">{item.label}</span>
              {item.description ? (
                <span className="text-xs text-slate-400">{item.description}</span>
              ) : null}
            </NavLink>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SecondaryNavigationGroup({
  title,
  navigation,
  onNavigate,
}: {
  readonly title: string;
  readonly navigation: WorkspaceSecondaryNavigation;
  readonly onNavigate?: () => void;
}) {
  if (navigation.status === "loading") {
    return (
      <section aria-label={`${title} navigation`} className="space-y-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</div>
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            // eslint-disable-next-line react/no-array-index-key
            <div key={index} className="h-9 rounded-lg bg-slate-100/80 animate-pulse" />
          ))}
        </div>
        <p className="text-xs text-slate-400">Loading navigation…</p>
      </section>
    );
  }

  if (navigation.items.length === 0) {
    return (
      <section aria-label={`${title} navigation`} className="space-y-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</div>
        <p className="rounded-lg border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-400">
          {navigation.emptyLabel}
        </p>
      </section>
    );
  }

  return (
    <NavigationGroup
      title={title}
      items={navigation.items.map((item) => ({ ...item, description: item.badge }))}
      onNavigate={onNavigate}
    />
  );
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M5 5l10 10M15 5l-10 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
