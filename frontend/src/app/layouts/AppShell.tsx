import { Outlet } from "react-router-dom";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";

import { AppProviders } from "@/providers/AppProviders";
import { RequireSession } from "@/providers/auth/RequireSession";

export function AppShell() {
  return (
    <NuqsAdapter>
      <AppProviders>
        <Outlet />
      </AppProviders>
    </NuqsAdapter>
  );
}

export function ProtectedLayout() {
  return (
    <RequireSession>
      <Outlet />
    </RequireSession>
  );
}
