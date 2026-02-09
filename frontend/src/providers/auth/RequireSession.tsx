import type { ReactNode } from "react";
import { useEffect } from "react";

import { createSearchParams, type Location, useLocation, useNavigate } from "react-router-dom";

import { useMfaStatusQuery } from "@/hooks/auth/useMfaStatusQuery";
import { useSessionQuery } from "@/hooks/auth/useSessionQuery";
import { useSetupStatusQuery } from "@/hooks/auth/useSetupStatusQuery";
import { Button } from "@/components/ui/button";

import { SessionProvider } from "./SessionContext";

interface RequireSessionProps {
  readonly children?: ReactNode;
}

const DEFAULT_RETURN_TO = "/";

function sanitizeReturnTo(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return null;
  }
  if (/[\u0000-\u001F\u007F]/.test(trimmed)) {
    return null;
  }
  return trimmed;
}

function getReturnToFromLocation(location: Location) {
  const fullPath = `${location.pathname}${location.search}${location.hash}`;
  return sanitizeReturnTo(fullPath) ?? DEFAULT_RETURN_TO;
}

function buildRedirectPath(basePath: string, returnTo: string) {
  if (!returnTo || returnTo === DEFAULT_RETURN_TO) {
    return basePath;
  }
  const query = createSearchParams({ returnTo }).toString();
  return `${basePath}?${query}`;
}

export function RequireSession({ children }: RequireSessionProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const sessionQuery = useSessionQuery();
  const { session, isLoading, isError, refetch } = sessionQuery;
  const mfaStatusQuery = useMfaStatusQuery({ enabled: Boolean(session) });
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
        const next = getReturnToFromLocation(location);
        navigate(buildRedirectPath("/setup", next), { replace: true });
        return;
      }
    }

    const next = getReturnToFromLocation(location);
    navigate(buildRedirectPath("/login", next), { replace: true });
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

  useEffect(() => {
    if (!session) {
      return;
    }
    if (location.pathname === "/mfa/setup") {
      return;
    }
    if (mfaStatusQuery.data?.onboardingRequired !== true) {
      return;
    }
    const next = getReturnToFromLocation(location);
    navigate(buildRedirectPath("/mfa/setup", next), { replace: true });
  }, [location, mfaStatusQuery.data?.onboardingRequired, navigate, session]);

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
        <Button variant="secondary" size="sm" onClick={() => refetch()}>
          Try again
        </Button>
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
          <Button variant="secondary" size="sm" onClick={() => refetchSetupStatus()}>
            Try again
          </Button>
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
