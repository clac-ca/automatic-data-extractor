import { useCallback, useEffect, useMemo, useState } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { fetchMfaStatus, type MfaStatusResponse } from "@/api/auth/api";
import { mapUiError } from "@/api/uiErrors";
import { navigateToPostAuthPath } from "@/lib/navigation/postAuthRedirect";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { MfaSetupFlow } from "@/features/mfa-setup";

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

function resolveReturnTo(value: string | null | undefined) {
  return sanitizeReturnTo(value) ?? DEFAULT_RETURN_TO;
}

export default function MfaSetupPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [mfaStatus, setMfaStatus] = useState<MfaStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const returnTo = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return resolveReturnTo(params.get("returnTo"));
  }, [location.search]);

  const refreshStatus = useCallback(async () => {
    setError(null);
    try {
      const next = await fetchMfaStatus();
      setMfaStatus(next);
    } catch (err) {
      const mapped = mapUiError(err, {
        fallback: "Unable to read MFA status right now.",
      });
      setError(mapped.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted-foreground">Loading MFA setup…</p>
      </div>
    );
  }

  if (error && !mfaStatus) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="secondary" onClick={() => void refreshStatus()}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-6 py-10">
      <section className="mb-6 space-y-3 rounded-2xl border border-border/80 bg-gradient-to-br from-card via-card to-accent/20 p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Security setup</p>
        <h1 className="text-2xl font-semibold text-foreground sm:text-3xl">Protect your account with MFA</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Use the guided flow to connect your authenticator app, verify a code, and save recovery codes.
          {mfaStatus?.onboardingRequired
            ? " MFA setup is required before you can continue."
            : " You can skip for now and set it up later from Account Settings."}
        </p>
        {error ? <Alert tone="danger">{error}</Alert> : null}
      </section>

      <MfaSetupFlow
        mfaStatus={mfaStatus}
        isMfaStatusLoading={isLoading}
        mfaStatusError={error}
        onRefreshMfaStatus={refreshStatus}
        allowSkip={Boolean(mfaStatus?.skipAllowed)}
        onboardingRequired={Boolean(mfaStatus?.onboardingRequired)}
        onSkip={() => navigateToPostAuthPath(navigate, returnTo, { replace: true })}
        onFlowComplete={() => navigateToPostAuthPath(navigate, returnTo, { replace: true })}
      />
    </div>
  );
}
