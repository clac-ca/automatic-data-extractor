import type { ReactNode } from "react";
import { useEffect } from "react";

import { useLocation, useNavigate } from "@app/navigation/history";

import { useSessionQuery } from "@hooks/auth/useSessionQuery";
import { useSetupStatusQuery } from "@hooks/auth/useSetupStatusQuery";
import { buildLoginRedirect, buildSetupRedirect, normalizeNextFromLocation } from "@utils/authNavigation";

import { SessionProvider } from "./SessionContext";

interface RequireSessionProps {
  readonly children?: ReactNode;
}

export function RequireSession({ children }: RequireSessionProps) {
  const location = useLocation();
  const navigate = useNavigate();
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

  useEffect(() => {
    if (session || isLoading || isError) {
      return;
    }

    if (shouldCheckSetup) {
      if (isSetupPending || isSetupError) {
        return;
      }

      if (isSetupSuccess && setupStatus?.setup_required) {
        const next = normalizeNextFromLocation(location);
        navigate(buildSetupRedirect(next), { replace: true });
        return;
      }
    }

    const next = normalizeNextFromLocation(location);
    navigate(buildLoginRedirect(next), { replace: true });
  }, [
    isError,
    isLoading,
    isSetupError,
    isSetupPending,
    isSetupSuccess,
    location,
    navigate,
    session,
    setupStatus?.setup_required,
    shouldCheckSetup,
  ]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        <p>Loading your workspace…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background text-center text-sm text-muted-foreground">
        <p>We were unable to confirm your session.</p>
        <button
          onClick={() => refetch()}
          className="focus-ring rounded-lg border border-border-strong bg-card px-4 py-2 font-semibold text-muted-foreground hover:bg-muted"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!session) {
    if (shouldCheckSetup && isSetupPending) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
          <p>Preparing initial setup…</p>
        </div>
      );
    }

    if (shouldCheckSetup && isSetupError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background text-center text-sm text-muted-foreground">
          <p>We were unable to check whether ADE is ready.</p>
          <button
            onClick={() => refetchSetupStatus()}
            className="focus-ring rounded-lg border border-border-strong bg-card px-4 py-2 font-semibold text-muted-foreground hover:bg-muted"
          >
            Try again
          </button>
        </div>
      );
    }

    return null;
  }

  return (
    <SessionProvider session={session} refetch={refetch}>
      {children ?? null}
    </SessionProvider>
  );
}
