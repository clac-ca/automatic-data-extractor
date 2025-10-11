import { Navigate, Outlet } from "react-router-dom";
import type { ReactNode } from "react";

import { useSetupStatusQuery } from "../../features/setup/hooks/useSetupStatusQuery";

interface RequireSetupCompleteProps {
  children?: ReactNode;
  pending?: ReactNode;
  error?: ReactNode;
  redirectTo?: string;
}

const DEFAULT_PENDING = (
  <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
    Checking setup status…
  </div>
);

const DEFAULT_ERROR = (
  <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
    <p>We were unable to determine the application setup state.</p>
    <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
      Try again
    </a>
  </div>
);

export function RequireSetupComplete({
  children,
  pending = DEFAULT_PENDING,
  error = DEFAULT_ERROR,
  redirectTo = "/setup",
}: RequireSetupCompleteProps) {
  const { data: setupStatus, isLoading, error: setupError } = useSetupStatusQuery();

  if (isLoading) {
    return <>{pending}</>;
  }

  if (setupError) {
    return <>{error}</>;
  }

  if (setupStatus?.requires_setup) {
    return <Navigate to={redirectTo} replace />;
  }

  if (children) {
    return <>{children}</>;
  }

  return <Outlet />;
}
