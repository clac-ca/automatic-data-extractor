import { useMemo, type ReactNode } from "react";
import clsx from "clsx";

import type { WorkspaceProfile } from "@/types/workspaces";
import type { WorkspaceNavigationItem } from "@/pages/Workspace/components/workspace-sidebar";
import { useWorkbenchWindow } from "@/pages/Workspace/context/WorkbenchWindowContext";
import { TopbarControls } from "@/components/topbar/TopbarControls";
import { TopbarSearch } from "@/components/topbar/TopbarSearch";
import { WorkspaceSidebar } from "@/pages/Workspace/components/workspace-sidebar";
import { Alert } from "@/components/ui/alert";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarStart,
  TopbarProvider,
} from "@/components/ui/topbar";

const DEFAULT_MAIN_ID = "main-content";
const SIDEBAR_COOKIE_NAME = "sidebar_state";

interface WorkspaceLayoutProps {
  readonly workspace: WorkspaceProfile;
  readonly navItems: readonly WorkspaceNavigationItem[];
  readonly contentKey: string;
  readonly fullHeight?: boolean;
  readonly fullWidth?: boolean;
  readonly safeModeEnabled?: boolean;
  readonly safeModeDetail?: string;
  readonly children: ReactNode;
}

function getSidebarDefaultOpen() {
  if (typeof document === "undefined") {
    return undefined;
  }

  const match = document.cookie.match(
    new RegExp(`(?:^|; )${SIDEBAR_COOKIE_NAME}=([^;]*)`),
  );
  if (!match) {
    return undefined;
  }

  return decodeURIComponent(match[1]) === "true";
}

function SkipToContent() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[var(--app-z-popover)] focus:rounded-lg focus:border focus:border-topbar-border focus:bg-topbar focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-topbar-foreground focus:shadow focus:outline-none focus:ring-2 focus:ring-topbar-ring focus:ring-offset-2 focus:ring-offset-background"
    >
      Skip to content
    </a>
  );
}

export function WorkspaceLayout({
  workspace,
  navItems,
  contentKey,
  fullHeight = false,
  fullWidth,
  safeModeEnabled = false,
  safeModeDetail,
  children,
}: WorkspaceLayoutProps) {
  const { session: workbenchSession, windowState } = useWorkbenchWindow();
  const immersiveWorkbenchActive = Boolean(workbenchSession && windowState === "maximized");

  const fullHeightLayout = fullHeight;
  const fullWidthLayout = fullWidth ?? fullHeightLayout;
  const contentHasPadding = !fullHeightLayout && !fullWidthLayout;

  const topbarSearch = useMemo(
    () => (
      <TopbarSearch
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

  const sidebar = immersiveWorkbenchActive ? null : <WorkspaceSidebar items={navItems} />;

  const topbar = immersiveWorkbenchActive ? null : (
    <Topbar position="static">
      <SkipToContent />
      <TopbarContent className="px-4 sm:px-6 lg:px-10">
        <TopbarStart className="gap-3">
          <SidebarTrigger />
        </TopbarStart>
        <TopbarCenter className="min-w-0">{topbarSearch}</TopbarCenter>
        <TopbarEnd>
          <TopbarControls />
        </TopbarEnd>
      </TopbarContent>
    </Topbar>
  );

  // When immersive is active we still must render *a sidebar node* to keep shell shape.
  // Use an empty fragment instead of null so the shell always has a sidebar element.
  const sidebarNode = sidebar ?? <></>;

  return (
    <TopbarProvider
      mode="expanded"
      style={{
        "--topbar-height": "3.5rem",
        "--topbar-height-compact": "3rem",
        "--topbar-height-mobile": "3.5rem",
      }}
    >
      <SidebarProvider
        className="min-h-svh w-full bg-background text-foreground"
        style={{
          "--sidebar-width": "13.5rem",
          "--sidebar-width-icon": "3rem",
          "--sidebar-width-mobile": "18rem",
        }}
        defaultOpen={getSidebarDefaultOpen()}
      >
        {/* MUST be direct siblings for shadcn sidebar peer/gap behavior */}
        {sidebarNode}

        <main className="relative flex min-h-svh w-full min-w-0 flex-1 flex-col bg-background">
          {/* Topbar must be inside the right column */}
          {topbar}

          {/* Single scroll container under the topbar */}
          <div id={DEFAULT_MAIN_ID} className="min-h-0 min-w-0 flex-1 overflow-auto">
            {/* This wrapper lives inside the shell's scroll container */}
            <div className="min-h-0 min-w-0" key={`section-${contentKey}`}>
              <div
                className={clsx(
                  fullHeightLayout
                    ? "flex min-h-0 w-full flex-col"
                    : fullWidthLayout
                      ? "flex w-full flex-col"
                      : "mx-auto flex w-full max-w-7xl flex-col px-6 py-6",
                )}
              >
                {safeModeEnabled && safeModeDetail ? (
                  <div
                    className={clsx(
                      "mb-4",
                      contentHasPadding ? "" : "px-6 pt-6",
                    )}
                  >
                    <Alert tone="warning" heading="Safe mode active">
                      {safeModeDetail}
                    </Alert>
                  </div>
                ) : null}

                <div className={clsx(fullHeightLayout ? "min-h-0 flex-1" : "")}>
                  {children}
                </div>
              </div>
            </div>
          </div>
        </main>
      </SidebarProvider>
    </TopbarProvider>
  );
}
