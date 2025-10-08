import { Navigate } from "react-router-dom";

import { useOptionalSession } from "../features/auth/hooks/useOptionalSession";
import { useSetupStatusQuery } from "../features/setup/hooks/useSetupStatusQuery";

export function RootRoute() {
  const { data: session, isLoading: isLoadingSession } = useOptionalSession();
  const { data: setupStatus, isLoading: isLoadingSetup, error: setupError } = useSetupStatusQuery();

  if (isLoadingSession || isLoadingSetup) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Loading…
      </div>
    );
  }

  if (setupError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to determine the application setup state.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
  }

  if (setupStatus?.requires_setup) {
    return <Navigate to="/setup" replace />;
  }

  if (session) {
    const preferredWorkspace = session.user.preferred_workspace_id ?? undefined;
    return <Navigate to={preferredWorkspace ? `/workspaces/${preferredWorkspace}` : "/workspaces"} replace />;
  }

  return <Navigate to="/login" replace />;
}
