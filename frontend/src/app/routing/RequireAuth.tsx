import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useSession } from "@hooks/useSession";

export function RequireAuth(): JSX.Element {
  const { isAuthenticated } = useSession();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
