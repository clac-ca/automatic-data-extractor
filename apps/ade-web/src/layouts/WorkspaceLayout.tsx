import { useMemo, type ReactElement } from "react";
import clsx from "clsx";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { GlobalNavSearch } from "@/components/navigation/GlobalNavSearch";
import { AppSidebar } from "@/components/navigation/AppSidebar";
import { Alert } from "@/components/ui/alert";
import { useAppTopBar } from "@/layouts/AppLayout";
import { useWorkbenchWindow } from "@/pages/Workspace/context/WorkbenchWindowContext";
import type { WorkspaceNavigationItem } from "@/pages/Workspace/components/workspaceNavigation";
import type { WorkspaceProfile } from "@/types/workspaces";

interface WorkspaceLayoutProps {
  readonly workspace: WorkspaceProfile;
  readonly navItems: readonly WorkspaceNavigationItem[];
  readonly contentKey: string;
  readonly children: ReactElement;
  readonly fullHeight?: boolean;
  readonly fullWidth?: boolean;
  readonly safeModeEnabled?: boolean;
  readonly safeModeDetail?: string;
}

export function WorkspaceLayout({
  workspace,
  navItems,
  contentKey,
  children,
  fullHeight,
  fullWidth,
  safeModeEnabled = false,
  safeModeDetail,
}: WorkspaceLayoutProps) {
  const { session: workbenchSession, windowState } = useWorkbenchWindow();

  const immersiveWorkbenchActive = Boolean(workbenchSession && windowState === "maximized");
  const fullHeightLayout = fullHeight ?? false;
  const fullWidthLayout = fullWidth ?? fullHeightLayout;
  const contentHasPadding = !fullHeightLayout && !fullWidthLayout;

  const topBarSearch = useMemo(
    () => (
      <GlobalNavSearch
        scope={{
          kind: "workspace",
          workspaceId: workspace.id,
          workspaceName: workspace.name,
          navItems,
        }}
      />
    ),
    [navItems, workspace.id, workspace.name],
  );

  const topBarLeading = useMemo(
    () => (
      <div className="flex min-w-0 items-center gap-3">
        <SidebarTrigger />
        <div className="hidden min-w-0 flex-col leading-tight sm:flex">
          <span className="text-[0.63rem] font-semibold uppercase tracking-[0.35em] text-muted-foreground">
            Workspace
          </span>
          <span className="truncate text-sm font-semibold text-foreground">{workspace.name}</span>
        </div>
      </div>
    ),
    [workspace.name],
  );

  const topBarConfig = useMemo(
    () =>
      immersiveWorkbenchActive
        ? { hidden: true }
        : {
            leading: topBarLeading,
            search: topBarSearch,
          },
    [immersiveWorkbenchActive, topBarLeading, topBarSearch],
  );

  useAppTopBar(topBarConfig);

  return (
    <div className="flex min-h-full min-w-0">
      {!immersiveWorkbenchActive ? <AppSidebar items={navItems} /> : null}
      <div
        className={clsx(
          "flex min-h-0 min-w-0 flex-1 flex-col",
          fullHeightLayout ? "overflow-hidden" : "overflow-visible",
        )}
      >
        <div className="relative flex min-h-0 min-w-0 flex-1" key={`section-${contentKey}`}>
          <div
            className={clsx(
              fullHeightLayout
                ? "flex w-full flex-1 min-h-0 flex-col px-0 py-0"
                : fullWidthLayout
                  ? "flex w-full flex-col px-0 py-0"
                  : "mx-auto flex w-full max-w-[var(--app-shell-content-max-width)] flex-col px-[var(--app-shell-content-padding-x)] py-[var(--app-shell-content-padding-y)]",
            )}
          >
            {safeModeEnabled && safeModeDetail ? (
              <div
                className={clsx(
                  "mb-4",
                  contentHasPadding
                    ? ""
                    : "px-[var(--app-shell-content-padding-x)] pt-[var(--app-shell-content-padding-y)]",
                )}
              >
                <Alert tone="warning" heading="Safe mode active">
                  {safeModeDetail}
                </Alert>
              </div>
            ) : null}
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
