import { useMemo, type ReactElement } from "react";
import clsx from "clsx";

import { AppTopBarControls } from "@/components/navigation/topbar/AppTopBarControls";
import { GlobalNavSearch } from "@/components/navigation/topbar/GlobalNavSearch";
import { WorkspaceSidebar } from "@/components/navigation/sidebar/WorkspaceSidebar";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
  TopbarStart,
} from "@/components/ui/topbar";
import { Alert } from "@/components/ui/alert";
import { AppLayout } from "@/layouts/AppLayout";
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

  const sidebarNode = useMemo(
    () => (!immersiveWorkbenchActive ? <WorkspaceSidebar items={navItems} /> : null),
    [immersiveWorkbenchActive, navItems],
  );

  const header = useMemo(() => {
    if (immersiveWorkbenchActive) {
      return null;
    }

    return (
      <Topbar position="static">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[var(--app-z-popover)] focus:rounded-lg focus:border focus:border-topbar-border focus:bg-topbar focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-topbar-foreground focus:shadow focus:outline-none focus:ring-2 focus:ring-topbar-ring focus:ring-offset-2 focus:ring-offset-background"
        >
          Skip to content
        </a>
        <TopbarContent className="px-4 sm:px-6 lg:px-10">
          <TopbarStart className="gap-3">
            <SidebarTrigger className="md:hidden" />
            <div className="flex min-w-0 items-center gap-3">
              <div className="hidden min-w-0 flex-col leading-tight sm:flex">
                <span className="text-[0.63rem] font-semibold uppercase tracking-[0.35em] text-muted-foreground">
                  Workspace
                </span>
                <span className="truncate text-sm font-semibold text-foreground">{workspace.name}</span>
              </div>
            </div>
          </TopbarStart>
          <TopbarCenter className="min-w-0">{topBarSearch}</TopbarCenter>
          <TopbarEnd>
            <AppTopBarControls />
          </TopbarEnd>
        </TopbarContent>
      </Topbar>
    );
  }, [immersiveWorkbenchActive, topBarSearch, workspace.name]);

  return (
    <TopbarProvider mode="expanded">
      <AppLayout header={header} sidebar={sidebarNode}>
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
      </AppLayout>
    </TopbarProvider>
  );
}
