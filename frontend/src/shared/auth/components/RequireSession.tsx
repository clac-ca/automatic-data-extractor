import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { SessionProvider } from "../context/SessionContext";
import { useSessionQuery } from "../hooks/useSessionQuery";
import { useSetupStatusQuery } from "../hooks/useSetupStatusQuery";
import { buildLoginRedirect, normalizeNextFromLocation } from "../utils/authNavigation";

export interface RequireSessionProps {
  readonly children?: ReactNode;
}

export function RequireSession({ children }: RequireSessionProps) {
  const location = useLocation();
  const sessionQuery = useSessionQuery();
  const { session, isLoading, isError, refetch } = sessionQuery;
  const shouldCheckSetup = !session && !isLoading && !isError;
  const {
    data: setupStatus,
    isPending: isSetupPending,
    isError: isSetupError,
    isSuccess: isSetupSuccess,
    refetch: refetchSetupStatus,
  } = useSetupStatusQuery(shouldCheckSetup);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
        <p>Loading your workspace…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50 text-center text-sm text-slate-500">
        <p>We were unable to confirm your session.</p>
        <button
          onClick={() => refetch()}
          className="focus-ring rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold text-slate-600 hover:bg-slate-100"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!session) {
    if (shouldCheckSetup && isSetupPending) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
          <p>Preparing initial setup…</p>
        </div>
      );
    }

    if (shouldCheckSetup && isSetupError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50 text-center text-sm text-slate-500">
          <p>We were unable to check whether ADE is ready.</p>
          <button
            onClick={() => refetchSetupStatus()}
            className="focus-ring rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold text-slate-600 hover:bg-slate-100"
          >
            Try again
          </button>
        </div>
      );
    }

    if (isSetupSuccess && setupStatus?.requires_setup) {
      return <Navigate to="/setup" replace />;
    }

    const next = normalizeNextFromLocation(location);

    return <Navigate to={buildLoginRedirect(next)} replace />;
  }

  if (children) {
    return (
      <SessionProvider session={session} refetch={refetch}>
        {children}
      </SessionProvider>
    );
  }

  return (
    <SessionProvider session={session} refetch={refetch}>
      <Outlet />
    </SessionProvider>
  );
}
