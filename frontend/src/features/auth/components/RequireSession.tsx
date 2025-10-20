import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useSessionQuery } from "../hooks/useSessionQuery";
import { SessionProvider } from "../context/SessionContext";

export interface RequireSessionProps {
  readonly redirectTo?: string;
  readonly children?: ReactNode;
}

export function RequireSession({ redirectTo = "/login", children }: RequireSessionProps) {
  const location = useLocation();
  const { session, isLoading, error, refetch } = useSessionQuery();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
        <p>Loading your workspace…</p>
      </div>
    );
  }

  if (error) {
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
    return (
      <Navigate
        to={redirectTo}
        replace
        state={{ next: location.pathname + location.search + location.hash }}
      />
    );
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
