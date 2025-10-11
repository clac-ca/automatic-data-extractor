import { Navigate, Outlet } from "react-router-dom";
import type { ReactNode } from "react";

import { useOptionalSession } from "../../features/auth/hooks/useOptionalSession";
import { resolveSessionDestination } from "../../features/auth/utils/resolveSessionDestination";

interface RequireNoSessionProps {
  children?: ReactNode;
  pending?: ReactNode;
  error?: ReactNode;
  redirectTo?: string;
}

const DEFAULT_PENDING = (
  <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
    Preparing sign-in…
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

export function RequireNoSession({
  children,
  pending = DEFAULT_PENDING,
  error = DEFAULT_ERROR,
  redirectTo = "/workspaces",
}: RequireNoSessionProps) {
  const { data: session, isLoading, error: sessionError } = useOptionalSession();

  if (isLoading) {
    return <>{pending}</>;
  }

  if (sessionError) {
    return <>{error}</>;
  }

  if (session) {
    return <Navigate to={resolveSessionDestination(session, redirectTo)} replace />;
  }

  if (children) {
    return <>{children}</>;
  }

  return <Outlet />;
}
