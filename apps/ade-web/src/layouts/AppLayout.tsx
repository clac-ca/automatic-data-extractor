import type { CSSProperties, ReactNode } from "react";

import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";

const DEFAULT_MAIN_ID = "main-content";

interface AppLayoutProps {
  readonly header?: ReactNode;
  readonly sidebar?: ReactNode;
  readonly children: ReactNode;
  readonly mainId?: string;
}

export function AppLayout({ header, sidebar, children, mainId = DEFAULT_MAIN_ID }: AppLayoutProps) {
  if (sidebar) {
    const sidebarStyle: CSSProperties = {
      "--sidebar-width": "var(--app-shell-sidebar-width)",
      "--sidebar-width-icon": "var(--app-shell-sidebar-collapsed-width)",
    };

    return (
      <SidebarProvider
        className="min-h-svh w-full bg-background text-foreground"
        style={sidebarStyle}
      >
        <AppLayoutWithSidebar header={header} sidebar={sidebar} mainId={mainId}>
          {children}
        </AppLayoutWithSidebar>
      </SidebarProvider>
    );
  }

  return (
    <div className="min-h-svh w-full bg-background text-foreground">
      <AppLayoutNoSidebar header={header} mainId={mainId}>
        {children}
      </AppLayoutNoSidebar>
    </div>
  );
}

interface AppLayoutGridProps {
  readonly header?: ReactNode;
  readonly sidebar?: ReactNode | null;
  readonly children: ReactNode;
  readonly mainId: string;
  readonly gridStyle: CSSProperties;
}

function AppLayoutGrid({ header, sidebar, children, mainId, gridStyle }: AppLayoutGridProps) {
  return (
    <div className="grid min-h-svh w-full flex-1" style={gridStyle}>
      {sidebar ? (
        <div style={{ gridArea: "sidebar" }} className="min-h-0 min-w-0">
          {sidebar}
        </div>
      ) : null}
      {header ? (
        <div style={{ gridArea: "header" }} className="min-h-0 min-w-0">
          {header}
        </div>
      ) : null}
      <main
        id={mainId}
        tabIndex={-1}
        className="min-h-0 min-w-0 overflow-y-auto"
        style={{ gridArea: "main" }}
      >
        {children}
      </main>
    </div>
  );
}

interface AppLayoutWithSidebarProps {
  readonly header?: ReactNode;
  readonly sidebar: ReactNode;
  readonly children: ReactNode;
  readonly mainId: string;
}

function AppLayoutWithSidebar({ header, sidebar, children, mainId }: AppLayoutWithSidebarProps) {
  const { state, isMobile } = useSidebar();
  const headerRow = header ? "var(--app-shell-header-height)" : "0px";
  const sidebarColumn = isMobile
    ? "0px"
    : state === "collapsed"
      ? "var(--app-shell-sidebar-collapsed-width)"
      : "var(--app-shell-sidebar-width)";

  const gridStyle: CSSProperties = {
    gridTemplateAreas: `"sidebar header" "sidebar main"`,
    gridTemplateColumns: `${sidebarColumn} minmax(0, 1fr)`,
    gridTemplateRows: `${headerRow} minmax(0, 1fr)`,
  };

  return (
    <AppLayoutGrid header={header} sidebar={sidebar} mainId={mainId} gridStyle={gridStyle}>
      {children}
    </AppLayoutGrid>
  );
}

interface AppLayoutNoSidebarProps {
  readonly header?: ReactNode;
  readonly children: ReactNode;
  readonly mainId: string;
}

function AppLayoutNoSidebar({ header, children, mainId }: AppLayoutNoSidebarProps) {
  const headerRow = header ? "var(--app-shell-header-height)" : "0px";
  const gridStyle: CSSProperties = {
    gridTemplateAreas: `"header" "main"`,
    gridTemplateColumns: "minmax(0, 1fr)",
    gridTemplateRows: `${headerRow} minmax(0, 1fr)`,
  };

  return (
    <AppLayoutGrid header={header} sidebar={null} mainId={mainId} gridStyle={gridStyle}>
      {children}
    </AppLayoutGrid>
  );
}
