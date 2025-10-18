import { Outlet } from "react-router-dom";

import { RequireSession } from "../../../features/auth/components/RequireSession";

export default function AppLayoutRoute() {
  return (
    <RequireSession>
      <Outlet />
    </RequireSession>
  );
}
