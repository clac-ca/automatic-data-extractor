import { ScrollRestoration } from "react-router";
import { Outlet } from "react-router";

import { AppProviders } from "./AppProviders";

export default function Root() {
  return (
    <AppProviders>
      <Outlet />
      <ScrollRestoration />
    </AppProviders>
  );
}
