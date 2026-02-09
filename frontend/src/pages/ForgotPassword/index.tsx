import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { z } from "zod";

import { createSearchParams, Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "@/api";
import { requestPasswordReset } from "@/api/auth/api";
import { useAuthProvidersQuery } from "@/hooks/auth/useAuthProvidersQuery";
import { useSessionQuery } from "@/hooks/auth/useSessionQuery";
import { useSetupStatusQuery } from "@/hooks/auth/useSetupStatusQuery";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";

const forgotPasswordSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your email address.")
    .email("Enter a valid email address."),
});

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

export default function ForgotPasswordScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const sessionQuery = useSessionQuery();
  const providersQuery = useAuthProvidersQuery();
  const { session, isLoading: sessionLoading, isError: sessionError } = sessionQuery;
  const shouldCheckSetup = !session && !sessionLoading && !sessionError;
  const setupQuery = useSetupStatusQuery(shouldCheckSetup);
  const authMode = providersQuery.data?.mode ?? "password_only";
  const passwordResetEnabled = providersQuery.data?.passwordResetEnabled ?? authMode !== "idp_only";
  const providersLoadFailed = providersQuery.isError && !providersQuery.isFetching;
  const returnTo = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return resolveReturnTo(params.get("returnTo"));
  }, [location.search]);
  const loginPath = useMemo(() => buildRedirectPath("/login", returnTo), [returnTo]);

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestComplete, setRequestComplete] = useState(false);
  const resetUnavailableMessage = authMode === "idp_only"
    ? "Password reset is managed by your organization's identity provider. Use SSO sign-in or contact your administrator."
    : "Password reset is unavailable. Contact your administrator.";

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
  }, [
    navigate,
    returnTo,
    setupQuery.data?.setup_required,
    setupQuery.isError,
    setupQuery.isPending,
    shouldCheckSetup,
  ]);

  if (sessionLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted-foreground">Checking your session...</p>
      </div>
    );
  }

  if (sessionError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">
          We were unable to verify your session. Refresh the page to try again.
        </p>
        <Button variant="secondary" onClick={() => sessionQuery.refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (setupQuery.isPending && shouldCheckSetup) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted-foreground">Preparing initial setup...</p>
      </div>
    );
  }

  if (setupQuery.isError && shouldCheckSetup) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">We were unable to check whether ADE is ready.</p>
        <Button variant="secondary" onClick={() => setupQuery.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!passwordResetEnabled) {
      setFormError(resetUnavailableMessage);
      return;
    }

    const formData = new FormData(event.currentTarget);
    const parsed = forgotPasswordSchema.safeParse(Object.fromEntries(formData.entries()));
    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? "Invalid input.";
      setFormError(message);
      return;
    }

    setIsSubmitting(true);
    try {
      await requestPasswordReset({ email: parsed.data.email });
      setRequestComplete(true);
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        if (error.status === 403) {
          setFormError(resetUnavailableMessage);
          return;
        }
        const detail = error.problem?.detail;
        const message =
          typeof detail === "string" ? detail : error.message || "Unable to request a password reset.";
        setFormError(message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Unable to request a password reset.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen flex-col justify-center bg-background px-6 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-border bg-card p-10 shadow-soft">
        <header className="space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Password recovery
          </p>
          <h1 className="text-3xl font-semibold text-foreground">Reset your password</h1>
          <p className="text-sm text-muted-foreground">
            Enter your account email and we&apos;ll process a password reset request.
          </p>
        </header>

        {requestComplete ? (
          <Alert tone="info" className="mt-6">
            If an account exists for that email, password reset instructions will be sent shortly.
          </Alert>
        ) : null}

        {providersLoadFailed ? (
          <Alert tone="warning" className="mt-6">
            We couldn't confirm password reset availability. You can still try submitting your email.
          </Alert>
        ) : null}

        {!passwordResetEnabled ? (
          <Alert tone="info" className="mt-6">
            {resetUnavailableMessage}
          </Alert>
        ) : null}

        {passwordResetEnabled ? (
          <form method="post" className="mt-8 space-y-6" onSubmit={handleSubmit}>
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

            {formError ? <Alert tone="danger">{formError}</Alert> : null}

            <Button type="submit" className="w-full justify-center" disabled={isSubmitting}>
              {isSubmitting ? "Sending..." : "Send reset instructions"}
            </Button>
          </form>
        ) : null}

        <div className="mt-6 text-center">
          <Link
            to={loginPath}
            className="text-sm font-medium text-muted-foreground transition hover:text-foreground"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
