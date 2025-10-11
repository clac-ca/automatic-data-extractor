import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useSessionQuery } from "../../features/auth/hooks/useSessionQuery";

interface RequireSessionProps {
  pending?: ReactNode;
  error?: ReactNode;
}

const DEFAULT_PENDING = (
  <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
    Loading workspace…
  </div>
);

const DEFAULT_ERROR = (
  <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
    <p>We were unable to confirm your session.</p>
    <a href="/login" className="font-medium text-sky-300 hover:text-sky-200">
      Return to sign in
    </a>
  </div>
);

export function RequireSession({ pending = DEFAULT_PENDING, error = DEFAULT_ERROR }: RequireSessionProps) {
  const location = useLocation();
  const { data: session, isLoading, error: sessionError } = useSessionQuery();

  if (isLoading) {
    return <>{pending}</>;
  }

  if (sessionError) {
    return <>{error}</>;
  }

  if (!session) {
    const returnTo = `${location.pathname}${location.search}${location.hash}`;
    const params = new URLSearchParams();
    if (returnTo && returnTo !== "/") {
      params.set("return_to", returnTo);
    }
    const loginPath = params.size > 0 ? `/login?${params.toString()}` : "/login";
    return <Navigate to={loginPath} replace />;
  }

  return <Outlet context={session} />;
}
