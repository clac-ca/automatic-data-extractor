import { Outlet } from "react-router-dom";

import { AppProviders } from "./AppProviders";

export default function RootRoute() {
  return (
    <AppProviders>
      <Outlet />
    </AppProviders>
  );
}

