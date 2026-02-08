import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { createSearchParams, Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "@/api";
import { createSession, sessionKeys, type AuthProvider, verifyMfaChallenge } from "@/api/auth/api";
import { useAuthProvidersQuery } from "@/hooks/auth/useAuthProvidersQuery";
import { useSessionQuery } from "@/hooks/auth/useSessionQuery";
import { useSetupStatusQuery } from "@/hooks/auth/useSetupStatusQuery";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your email address.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

const DEFAULT_RETURN_TO = "/";

function buildSsoHref(startUrl: string | null | undefined, returnTo: string | null) {
  const base = (startUrl ?? "").trim();
  if (!base) {
    return "#";
  }
  if (!returnTo) {
    return base;
  }
  const joiner = base.includes("?") ? "&" : "?";
  return `${base}${joiner}returnTo=${encodeURIComponent(returnTo)}`;
}

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

function pickReturnTo(sessionReturnTo: string | null | undefined, fallback: string | null | undefined) {
  const sessionPath = sanitizeReturnTo(sessionReturnTo);
  if (sessionPath) {
    return sessionPath;
  }
  const fallbackPath = sanitizeReturnTo(fallback);
  if (fallbackPath) {
    return fallbackPath;
  }
  return DEFAULT_RETURN_TO;
}

function buildRedirectPath(basePath: string, returnTo: string | null | undefined) {
  const safeReturnTo = sanitizeReturnTo(returnTo);
  if (!safeReturnTo || safeReturnTo === DEFAULT_RETURN_TO) {
    return basePath;
  }
  const query = createSearchParams({ returnTo: safeReturnTo }).toString();
  return `${basePath}?${query}`;
}

export default function LoginScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const sessionQuery = useSessionQuery();
  const { session, isLoading: sessionLoading, isError: sessionError } = sessionQuery;
  const shouldCheckSetup = !session && !sessionLoading && !sessionError;
  const setupQuery = useSetupStatusQuery(shouldCheckSetup);

  const providersQuery = useAuthProvidersQuery();
  const providers: AuthProvider[] = providersQuery.data?.providers ?? [];
  const oidcProviders = providers.filter((provider) => provider.type === "oidc");
  const forceSso = providersQuery.data?.forceSso ?? false;
  const passwordResetEnabled = providersQuery.data?.passwordResetEnabled ?? !forceSso;
  const providersLoadFailed = providersQuery.isError && !providersQuery.isFetching;
  const providersUnavailable = oidcProviders.length === 0;
  const blockingSsoMessage =
    forceSso && (providersLoadFailed || providersUnavailable)
      ? "Single sign-on is required, but no providers are available. Contact your administrator."
      : null;
  const providersError =
    providersLoadFailed && !forceSso
      ? "We couldn't load the list of providers. Refresh the page or continue with email."
      : null;

  const returnTo = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return resolveReturnTo(params.get("returnTo"));
  }, [location.search]);
  const forgotPasswordPath = useMemo(
    () => buildRedirectPath("/forgot-password", returnTo),
    [returnTo],
  );

  useEffect(() => {
    if (!session) {
      return;
    }
    navigate(pickReturnTo(session.return_to, returnTo), { replace: true });
  }, [navigate, returnTo, session]);

  useEffect(() => {
    if (!shouldCheckSetup) {
      return;
    }
    if (setupQuery.isPending || setupQuery.isError) {
      return;
    }
    if (setupQuery.data?.setup_required) {
      navigate(buildRedirectPath("/setup", returnTo), { replace: true });
    }
  }, [navigate, returnTo, setupQuery.data?.setup_required, setupQuery.isError, setupQuery.isPending, shouldCheckSetup]);

  const ssoErrorMessage = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get("ssoError");
    if (!code) {
      return null;
    }
    const providerId = params.get("providerId");
    const providerLabel = oidcProviders.find((provider) => provider.id === providerId)?.label;

    const prefix = providerLabel ? `${providerLabel} sign-in failed.` : "Single sign-on failed.";
    switch (code) {
      case "PROVIDER_NOT_FOUND":
        return `${prefix} The provider is no longer available.`;
      case "PROVIDER_DISABLED":
        return `${prefix} The provider is disabled.`;
      case "PROVIDER_MISCONFIGURED":
        return `${prefix} The provider is misconfigured. Contact your administrator.`;
      case "STATE_INVALID":
      case "STATE_EXPIRED":
      case "STATE_REUSED":
        return `${prefix} Your sign-in session expired. Please try again.`;
      case "TOKEN_EXCHANGE_FAILED":
        return `${prefix} We couldn't complete the sign-in. Try again.`;
      case "ID_TOKEN_INVALID":
        return `${prefix} We couldn't validate your sign-in. Contact your administrator.`;
      case "EMAIL_MISSING":
        return `${prefix} Your identity provider did not return an email address.`;
      case "EMAIL_NOT_VERIFIED":
        return `${prefix} Your email address must be verified before signing in.`;
      case "AUTO_PROVISION_DISABLED":
        return `${prefix} Your account must be provisioned before signing in.`;
      case "DOMAIN_NOT_ALLOWED":
        return `${prefix} Your domain is not approved for auto-provisioning.`;
      case "USER_NOT_ALLOWED":
        return `${prefix} Your account is not allowed to sign in.`;
      case "IDENTITY_CONFLICT":
        return `${prefix} Your account is linked to another user. Contact your administrator.`;
      case "UPSTREAM_ERROR":
        return `${prefix} The identity provider returned an error.`;
      case "RATE_LIMITED":
        return `${prefix} Too many attempts. Please wait and try again.`;
      case "INTERNAL_ERROR":
        return `${prefix} We couldn't complete the sign-in. Please try again.`;
      default:
        return `${prefix} Please try again.`;
    }
  }, [location.search, oidcProviders]);
  const passwordResetMessage = useMemo(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("passwordReset") === "success") {
      return "Your password was reset. Sign in with your new password.";
    }
    return null;
  }, [location.search]);

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mfaChallengeToken, setMfaChallengeToken] = useState<string | null>(null);

  useEffect(() => {
    setFormError(null);
  }, [location.search]);

  if (sessionLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted-foreground">Checking your session…</p>
      </div>
    );
  }

  if (sessionError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">We were unable to verify your session. Refresh the page to try again.</p>
        <Button variant="secondary" onClick={() => sessionQuery.refetch()}>Retry</Button>
      </div>
    );
  }

  if (setupQuery.isPending && shouldCheckSetup) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted-foreground">Preparing initial setup…</p>
      </div>
    );
  }

  if (setupQuery.isError && shouldCheckSetup) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">We were unable to check whether ADE is ready.</p>
        <Button variant="secondary" onClick={() => setupQuery.refetch()}>Try again</Button>
      </div>
    );
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const formData = new FormData(event.currentTarget);
    const raw = Object.fromEntries(formData.entries());
    const parsed = loginSchema.safeParse(raw);

    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? "Invalid input.";
      setFormError(message);
      return;
    }

    const { email, password } = parsed.data;
    const redirectValue = typeof raw.returnTo === "string" ? raw.returnTo : null;
    const destination = resolveReturnTo(redirectValue);

    setIsSubmitting(true);
    try {
      const result = await createSession({ email, password });
      if (result.kind === "mfa_required") {
        setMfaChallengeToken(result.challengeToken);
        return;
      }
      queryClient.setQueryData(sessionKeys.detail(), result.session);
      const nextPath = pickReturnTo(result.session.return_to, destination);
      if (result.mfaSetupRequired || result.mfaSetupRecommended) {
        navigate(buildRedirectPath("/mfa/setup", nextPath), { replace: true });
        return;
      }
      navigate(nextPath, { replace: true });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        const message = error.problem?.detail ?? error.message ?? "Unable to sign in.";
        setFormError(message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Unable to sign in.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!mfaChallengeToken) {
      setFormError("MFA challenge is missing. Please sign in again.");
      return;
    }

    const formData = new FormData(event.currentTarget);
    const code = String(formData.get("code") ?? "").trim();
    if (!code) {
      setFormError("Enter your authentication code.");
      return;
    }

    setIsSubmitting(true);
    try {
      const nextSession = await verifyMfaChallenge({
        challengeToken: mfaChallengeToken,
        code,
      });
      queryClient.setQueryData(sessionKeys.detail(), nextSession);
      navigate(pickReturnTo(nextSession.return_to, returnTo), { replace: true });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        const message = error.problem?.detail ?? error.message ?? "Unable to verify MFA challenge.";
        setFormError(message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Unable to verify MFA challenge.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const shouldShowActionError = Boolean(formError) && !isSubmitting;
  const isProvidersLoading = providersQuery.isLoading || providersQuery.isFetching;

  return (
    <div className="mx-auto flex min-h-screen flex-col justify-center bg-background px-6 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-border bg-card p-10 shadow-soft">
        <header className="space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Welcome back</p>
          <h1 className="text-3xl font-semibold text-foreground">Sign in to ADE</h1>
          <p className="text-sm text-muted-foreground">
            Enter your email and password or continue with a connected provider.
          </p>
        </header>

        {passwordResetMessage ? <Alert tone="info" className="mt-6">{passwordResetMessage}</Alert> : null}
        {ssoErrorMessage ? <Alert tone="danger" className="mt-6">{ssoErrorMessage}</Alert> : null}
        {blockingSsoMessage ? <Alert tone="danger" className="mt-6">{blockingSsoMessage}</Alert> : null}
        {providersError ? <Alert tone="warning" className="mt-6">{providersError}</Alert> : null}

        {isProvidersLoading ? (
          <div className="mt-6 space-y-3">
            <div className="h-10 animate-pulse rounded-lg bg-muted" />
            <div className="h-10 animate-pulse rounded-lg bg-muted" />
          </div>
        ) : !blockingSsoMessage && oidcProviders.length > 0 ? (
          <div className="mt-6 space-y-3">
            {oidcProviders.map((provider) => (
              <a
                key={provider.id}
                href={buildSsoHref(provider.startUrl, returnTo)}
                className="flex w-full items-center justify-center rounded-lg border border-border bg-card px-4 py-2 text-sm font-semibold text-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                Continue with {provider.label}
              </a>
            ))}
          </div>
        ) : null}

        {!forceSso && !mfaChallengeToken ? (
          <form method="post" className="mt-8 space-y-6" onSubmit={handleSubmit}>
            <input type="hidden" name="returnTo" value={returnTo} />
            <FormField label="Email address" required>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                name="email"
                disabled={isSubmitting}
              />
            </FormField>

            <FormField label="Password" required>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                name="password"
                disabled={isSubmitting}
              />
            </FormField>

            {passwordResetEnabled ? (
              <div className="text-right">
                <Link
                  to={forgotPasswordPath}
                  className="text-sm font-medium text-muted-foreground transition hover:text-foreground"
                >
                  Forgot your password?
                </Link>
              </div>
            ) : (
              <p className="text-right text-sm text-muted-foreground">
                Password reset is unavailable. Contact your administrator.
              </p>
            )}

            {shouldShowActionError ? <Alert tone="danger">{formError}</Alert> : null}

            <Button type="submit" className="w-full justify-center" disabled={isSubmitting}>
              {isSubmitting ? "Signing in…" : "Continue"}
            </Button>
          </form>
        ) : null}

        {!forceSso && mfaChallengeToken ? (
          <form method="post" className="mt-8 space-y-6" onSubmit={handleMfaSubmit}>
            <FormField label="Authentication code" required>
              <Input
                id="code"
                type="text"
                autoComplete="one-time-code"
                placeholder="123456 or XXXX-XXXX"
                name="code"
                disabled={isSubmitting}
              />
            </FormField>

            {shouldShowActionError ? <Alert tone="danger">{formError}</Alert> : null}

            <div className="space-y-2">
              <Button type="submit" className="w-full justify-center" disabled={isSubmitting}>
                {isSubmitting ? "Verifying…" : "Verify and continue"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                className="w-full justify-center"
                disabled={isSubmitting}
                onClick={() => {
                  setMfaChallengeToken(null);
                  setFormError(null);
                }}
              >
                Back to password login
              </Button>
            </div>
          </form>
        ) : null}

        {forceSso ? (
          <Alert tone="info" className="mt-8">
            Password sign-in is disabled for this deployment. Use one of the configured providers above.
          </Alert>
        ) : null}
      </div>
    </div>
  );
}
