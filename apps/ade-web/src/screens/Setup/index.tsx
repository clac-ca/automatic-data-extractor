import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { useLocation, useNavigate } from "@app/nav/history";
import { ApiError } from "@shared/api";
import { sessionKeys } from "@shared/auth/api";
import { useSetupStatusQuery } from "@shared/auth/hooks/useSetupStatusQuery";
import {
  buildLoginRedirect,
  chooseDestination,
  resolveRedirectParam,
} from "@shared/auth/utils/authNavigation";
import { completeSetup } from "@shared/setup/api";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";

const setupSchema = z
  .object({
    displayName: z.string().min(1, "Display name is required."),
    email: z
      .string()
      .min(1, "Email is required.")
      .email("Enter a valid email address."),
    password: z.string().min(12, "Use at least 12 characters."),
    confirmPassword: z.string().min(1, "Confirm your password."),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match.",
  });

interface SetupFormValues {
  displayName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export default function SetupScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const setupQuery = useSetupStatusQuery(true);
  const redirectTo = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return resolveRedirectParam(params.get("redirectTo"));
  }, [location.search]);

  useEffect(() => {
    if (setupQuery.isPending || setupQuery.isError) {
      return;
    }
    if (!setupQuery.data?.setup_required) {
      navigate(buildLoginRedirect(redirectTo), { replace: true });
    }
  }, [navigate, redirectTo, setupQuery.data?.setup_required, setupQuery.isError, setupQuery.isPending]);

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (setupQuery.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted-foreground">Loading setup status…</p>
      </div>
    );
  }

  if (setupQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">We couldn't check whether ADE requires initial setup.</p>
        <Button variant="secondary" onClick={() => setupQuery.refetch()}>Try again</Button>
      </div>
    );
  }

  if (!setupQuery.data?.setup_required) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const formData = new FormData(event.currentTarget);
    const raw = Object.fromEntries(formData.entries()) as Partial<SetupFormValues> & { redirectTo?: string };
    const parsed = setupSchema.safeParse(raw);

    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? "Invalid input.";
      setFormError(message);
      return;
    }

    setIsSubmitting(true);
    const destination = resolveRedirectParam(raw.redirectTo);

    try {
      const session = await completeSetup({
        display_name: parsed.data.displayName,
        email: parsed.data.email,
        password: parsed.data.password,
      });
      queryClient.setQueryData(sessionKeys.detail(), session);
      navigate(chooseDestination(session.return_to, destination), { replace: true });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        const message = error.problem?.detail ?? error.message ?? "Setup failed. Try again.";
        setFormError(message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Setup failed. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center bg-background px-6 py-16">
      <div className="rounded-2xl border border-border bg-card p-10 shadow-soft">
        <header className="space-y-3 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            First-run configuration
          </p>
          <h1 className="text-3xl font-semibold text-foreground">Create the first administrator</h1>
          <p className="text-sm text-muted-foreground">
            Provide credentials for the inaugural administrator account. We'll redirect after completion.
          </p>
        </header>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <input type="hidden" name="redirectTo" value={redirectTo} />
          <div className="grid gap-6 md:grid-cols-2">
            <FormField label="Display name" required>
              <Input
                id="displayName"
                name="displayName"
                placeholder="Casey Operator"
                required
                disabled={isSubmitting}
              />
            </FormField>
            <FormField label="Email" required>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="casey@example.com"
                required
                disabled={isSubmitting}
              />
            </FormField>
          </div>

          <FormField label="Password" hint="Use at least 12 characters." required>
            <Input
              id="password"
              name="password"
              type="password"
              minLength={12}
              placeholder="••••••••••••"
              required
              disabled={isSubmitting}
            />
          </FormField>

          <FormField label="Confirm password" required>
            <Input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              minLength={12}
              placeholder="Re-enter your password"
              required
              disabled={isSubmitting}
            />
          </FormField>

          {formError ? <Alert tone="danger">{formError}</Alert> : null}

          <div className="flex justify-end">
            <Button type="submit" isLoading={isSubmitting} disabled={isSubmitting}>
              {isSubmitting ? "Creating administrator…" : "Create administrator"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
