import type { ReactNode } from "react";

import { useWorkspaceChrome } from "./WorkspaceChromeContext";

interface WorkspaceChromeProps {
  header: ReactNode;
  rail: ReactNode;
  children: ReactNode;
}

const EXPANDED_WIDTH = 288;
const COLLAPSED_WIDTH = 72;

export function WorkspaceChrome({ header, rail, children }: WorkspaceChromeProps) {
  const { isDesktop, isRailCollapsed, isOverlayOpen, closeOverlay } = useWorkspaceChrome();

  const templateColumns = isDesktop
    ? `${isRailCollapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH}px minmax(0, 1fr)`
    : "minmax(0, 1fr)";

  const templateAreas = isDesktop ? '"header header" "rail canvas"' : '"header" "canvas"';

  return (
    <div className="relative min-h-screen bg-slate-950 text-slate-100">
      <div
        className="grid min-h-screen"
        style={{
          gridTemplateAreas: templateAreas,
          gridTemplateColumns: templateColumns,
          gridTemplateRows: "auto 1fr",
        }}
      >
        <header
          style={{ gridArea: "header" }}
          className="z-20 border-b border-slate-900 bg-slate-950/80"
          role="banner"
          aria-label="Workspace chrome header"
        >
          {header}
        </header>
        {isDesktop ? (
          <aside
            style={{ gridArea: "rail" }}
            className="relative flex h-full min-h-0 border-r border-slate-900 bg-slate-950/80"
            aria-label="Workspace navigation"
          >
            {rail}
          </aside>
        ) : null}
        <main
          style={{ gridArea: "canvas" }}
          className="relative flex min-h-0 flex-col overflow-hidden bg-slate-950"
          role="main"
        >
          {children}
        </main>
      </div>
      {!isDesktop && isOverlayOpen ? (
        <>
          <div className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm" onClick={closeOverlay} aria-hidden="true" />
          <aside className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col border-r border-slate-900 bg-slate-950/95 shadow-2xl" aria-label="Workspace navigation">
            {rail}
          </aside>
        </>
      ) : null}
    </div>
  );
}
