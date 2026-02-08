import type { ReactNode } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import {
  AuthenticatedTopbarProvider,
  useAuthenticatedTopbarConfig,
} from "@/app/layouts/components/topbar/AuthenticatedTopbarContext";
import { UnifiedTopbarControls } from "@/app/layouts/components/topbar/UnifiedTopbarControls";
import { Button } from "@/components/ui/button";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
  TopbarStart,
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
  return (
    <TopbarProvider>
      <AuthenticatedTopbarProvider>
        <AuthenticatedLayoutInner />
      </AuthenticatedTopbarProvider>
    </TopbarProvider>
  );
}

function AuthenticatedLayoutInner() {
  const topbarConfig = useAuthenticatedTopbarConfig();
  const location = useLocation();
  const isOrganizationRoute =
    location.pathname === "/organization" || location.pathname.startsWith("/organization/");
  const shouldRenderTopbarStart = isOrganizationRoute || Boolean(topbarConfig?.mobileAction);

  const topbar = (
    <Topbar className="shadow-sm">
      <SkipToContent />
      <TopbarContent maxWidth="full" className="px-4 sm:px-6 lg:px-8">
        {shouldRenderTopbarStart ? (
          <TopbarStart className="relative z-10">
            {isOrganizationRoute ? (
              <Button asChild variant="outline" size="sm" className="h-9">
                <Link to="/workspaces">
                  <ArrowLeft className="size-4" />
                  <span>Go back to workspace</span>
                </Link>
              </Button>
            ) : null}
            {topbarConfig?.mobileAction ? (
              <div className="md:hidden">{topbarConfig.mobileAction}</div>
            ) : null}
          </TopbarStart>
        ) : null}
        <TopbarCenter className="hidden md:flex">
          {topbarConfig?.desktopCenter ?? null}
        </TopbarCenter>
        <TopbarEnd>
          <UnifiedTopbarControls />
        </TopbarEnd>
      </TopbarContent>
    </Topbar>
  );

  return (
    <div className="flex min-h-svh w-full flex-col bg-background text-foreground">
      <TopbarFrame topbar={topbar}>
        <Outlet />
      </TopbarFrame>
    </div>
  );
}
