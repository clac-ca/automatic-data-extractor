import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";

import { TopbarControls } from "@/components/topbar/TopbarControls";
import { TopbarSearch } from "@/components/topbar/TopbarSearch";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
} from "@/components/ui/topbar";

const DEFAULT_MAIN_ID = "main-content";

function SkipToContent() {
  return (
    <a
      href={`#${DEFAULT_MAIN_ID}`}
      className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[var(--app-z-popover)] focus:rounded-lg focus:border focus:border-topbar-border focus:bg-topbar focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-topbar-foreground focus:shadow focus:outline-none focus:ring-2 focus:ring-topbar-ring focus:ring-offset-2 focus:ring-offset-background"
    >
      Skip to content
    </a>
  );
}

export function TopbarFrame({
  topbar,
  children,
  mainId = DEFAULT_MAIN_ID,
}: {
  readonly topbar: ReactNode;
  readonly children: ReactNode;
  readonly mainId?: string;
}) {
  return (
    <>
      {topbar}
      <div id={mainId} className="min-h-0 min-w-0 flex-1 overflow-auto">
        {children}
      </div>
    </>
  );
}

export function AuthenticatedLayout() {
  const topbar = (
    <Topbar position="static">
      <SkipToContent />
      <TopbarContent className="px-4 sm:px-6 lg:px-10">
        <TopbarCenter className="min-w-0">
          <TopbarSearch scope={{ kind: "directory" }} />
        </TopbarCenter>
        <TopbarEnd>
          <TopbarControls />
        </TopbarEnd>
      </TopbarContent>
    </Topbar>
  );

  return (
    <TopbarProvider>
      <div className="flex min-h-svh w-full flex-col bg-background text-foreground">
        <TopbarFrame topbar={topbar}>
          <Outlet />
        </TopbarFrame>
      </div>
    </TopbarProvider>
  );
}
