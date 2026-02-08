import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { z } from "zod";

import { createSearchParams, Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "@/api";
import { completePasswordReset } from "@/api/auth/api";
import { useAuthProvidersQuery } from "@/hooks/auth/useAuthProvidersQuery";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";

const resetPasswordSchema = z
  .object({
    newPassword: z.string().min(12, "Use at least 12 characters."),
    confirmPassword: z.string().min(1, "Confirm your new password."),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match.",
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

function buildRedirectPath(basePath: string, returnTo: string | null | undefined) {
  const safeReturnTo = sanitizeReturnTo(returnTo);
  if (!safeReturnTo || safeReturnTo === DEFAULT_RETURN_TO) {
    return basePath;
  }
  const query = createSearchParams({ returnTo: safeReturnTo }).toString();
  return `${basePath}?${query}`;
}

function buildPostResetLoginPath(returnTo: string | null | undefined) {
  const safeReturnTo = sanitizeReturnTo(returnTo);
  const query = createSearchParams(
    safeReturnTo && safeReturnTo !== DEFAULT_RETURN_TO
      ? { passwordReset: "success", returnTo: safeReturnTo }
      : { passwordReset: "success" },
  ).toString();
  return `/login?${query}`;
}

export default function ResetPasswordScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const providersQuery = useAuthProvidersQuery();
  const forceSso = providersQuery.data?.forceSso ?? false;
  const passwordResetEnabled = providersQuery.data?.passwordResetEnabled ?? !forceSso;
  const resetUnavailableMessage = forceSso
    ? "Password reset is managed by your organization's identity provider. Use SSO sign-in or contact your administrator."
    : "Password reset is unavailable. Contact your administrator.";

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const returnTo = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return resolveReturnTo(params.get("returnTo"));
  }, [location.search]);
  const tokenFromQuery = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return (params.get("token") ?? "").trim();
  }, [location.search]);
  const loginPath = useMemo(
    () => buildRedirectPath("/login", returnTo),
    [returnTo],
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!passwordResetEnabled) {
      setFormError(resetUnavailableMessage);
      return;
    }
    if (!tokenFromQuery) {
      setFormError("Reset link is invalid or incomplete. Request a new reset email.");
      return;
    }

    const formData = new FormData(event.currentTarget);
    const parsed = resetPasswordSchema.safeParse(Object.fromEntries(formData.entries()));

    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? "Invalid input.";
      setFormError(message);
      return;
    }

    setIsSubmitting(true);
    try {
      await completePasswordReset({
        token: tokenFromQuery,
        newPassword: parsed.data.newPassword,
      });
      navigate(buildPostResetLoginPath(returnTo), { replace: true });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        if (error.status === 403) {
          setFormError(resetUnavailableMessage);
          return;
        }
        const message = error.problem?.detail ?? error.message ?? "Unable to reset password.";
        setFormError(message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Unable to reset password.");
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
          <h1 className="text-3xl font-semibold text-foreground">Choose a new password</h1>
          <p className="text-sm text-muted-foreground">
            Use the secure link from your email to set a new password for your account.
          </p>
        </header>

        {!passwordResetEnabled ? (
          <Alert tone="info" className="mt-6">
            {resetUnavailableMessage}
          </Alert>
        ) : null}

        {!tokenFromQuery && passwordResetEnabled ? (
          <Alert tone="warning" className="mt-6">
            This reset link is missing its token. Request a new password reset email and use the full link.
          </Alert>
        ) : null}

        {passwordResetEnabled ? (
          <form method="post" className="mt-8 space-y-6" onSubmit={handleSubmit}>
            <FormField label="New password" hint="Use at least 12 characters." required>
              <Input
                id="newPassword"
                name="newPassword"
                type="password"
                autoComplete="new-password"
                minLength={12}
                placeholder="••••••••••••"
                disabled={isSubmitting || !tokenFromQuery}
              />
            </FormField>

            <FormField label="Confirm new password" required>
              <Input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                minLength={12}
                placeholder="Re-enter your new password"
                disabled={isSubmitting || !tokenFromQuery}
              />
            </FormField>

            {formError ? <Alert tone="danger">{formError}</Alert> : null}

            <Button
              type="submit"
              className="w-full justify-center"
              disabled={isSubmitting || !tokenFromQuery}
            >
              {isSubmitting ? "Resetting…" : "Reset password"}
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
