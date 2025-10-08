import { Outlet, Navigate, useLocation } from "react-router-dom";

import { useSessionQuery } from "../hooks/useSessionQuery";

export function RequireSession() {
  const location = useLocation();
  const { data, isLoading, error } = useSessionQuery();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Loading workspace…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to confirm your session.</p>
        <a href="/login" className="font-medium text-sky-300 hover:text-sky-200">
          Return to sign in
        </a>
      </div>
    );
  }

  if (!data) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet context={data} />;
}
