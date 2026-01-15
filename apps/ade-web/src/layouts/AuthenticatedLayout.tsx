import { Outlet } from "react-router-dom";

import { AppTopBarControls } from "@/components/navigation/topbar/AppTopBarControls";
import { GlobalNavSearch } from "@/components/navigation/topbar/GlobalNavSearch";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
} from "@/components/ui/topbar";
import { AppLayout } from "@/layouts/AppLayout";

export function AuthenticatedLayout() {
  const header = (
    <Topbar position="static">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[var(--app-z-popover)] focus:rounded-lg focus:border focus:border-topbar-border focus:bg-topbar focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-topbar-foreground focus:shadow focus:outline-none focus:ring-2 focus:ring-topbar-ring focus:ring-offset-2 focus:ring-offset-background"
      >
        Skip to content
      </a>
      <TopbarContent className="px-4 sm:px-6 lg:px-10">
        <TopbarCenter className="min-w-0">
          <GlobalNavSearch scope={{ kind: "directory" }} />
        </TopbarCenter>
        <TopbarEnd>
          <AppTopBarControls />
        </TopbarEnd>
      </TopbarContent>
    </Topbar>
  );

  return (
    <TopbarProvider mode="expanded">
      <AppLayout header={header}>
        <Outlet />
      </AppLayout>
    </TopbarProvider>
  );
}
