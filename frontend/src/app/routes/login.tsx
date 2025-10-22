import { Form, redirect, useActionData, useLoaderData, useNavigation } from "react-router";
import type {
  ClientActionFunctionArgs,
  ClientLoaderFunctionArgs,
  ShouldRevalidateFunctionArgs,
} from "react-router";
import { z } from "zod";

import { ApiError } from "@shared/api";
import { createSession, fetchSession } from "@shared/auth/api";
import { useAuthProvidersQuery } from "@shared/auth/hooks/useAuthProvidersQuery";
import {
  DEFAULT_APP_HOME,
  chooseDestination,
  sanitizeNextPath,
} from "@shared/auth/utils/authNavigation";
import { fetchSetupStatus } from "@shared/setup/api";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your email address.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

export async function clientLoader({ request }: ClientLoaderFunctionArgs) {
  const url = new URL(request.url);
  const redirectTo = sanitizeNextPath(url.searchParams.get("redirectTo")) ?? DEFAULT_APP_HOME;

  const session = await fetchSession({ signal: request.signal });
  if (session) {
    throw redirect(chooseDestination(session.return_to, redirectTo));
  }

  const status = await fetchSetupStatus({ signal: request.signal });
  if (status.requires_setup) {
    throw redirect("/setup");
  }

  return { redirectTo };
}

export async function clientAction({ request }: ClientActionFunctionArgs) {
  const formData = await request.formData();
  const raw = Object.fromEntries(formData);
  const parsed = loginSchema.safeParse(raw);

  if (!parsed.success) {
    const message = parsed.error.issues[0]?.message ?? "Invalid input.";
    return { error: message };
  }

  const { email, password } = parsed.data;
  const redirectTo =
    sanitizeNextPath(typeof raw.redirectTo === "string" ? raw.redirectTo : null) ?? DEFAULT_APP_HOME;

  try {
    const session = await createSession({ email, password }, { signal: request.signal });
    throw redirect(chooseDestination(session.return_to, redirectTo));
  } catch (error: unknown) {
    if (error instanceof Response) {
      throw error;
    }
    if (error instanceof ApiError) {
      const message = error.problem?.detail ?? error.message ?? "Unable to sign in.";
      return { error: message };
    }
    return {
      error: error instanceof Error ? error.message : "Unable to sign in.",
    };
  }
}

export default function LoginRoute() {
  const loaderData = useLoaderData<typeof clientLoader>();
  const redirectTo = loaderData?.redirectTo ?? DEFAULT_APP_HOME;
  const providersQuery = useAuthProvidersQuery();
  const providers = providersQuery.data?.providers ?? [];
  const forceSso = providersQuery.data?.force_sso ?? false;
  const providersError =
    providersQuery.isError && !providersQuery.isFetching
      ? "We couldn't load the list of providers. Refresh the page or continue with email."
      : null;
  const actionData = useActionData<LoginActionError>();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";
  const isProvidersLoading = providersQuery.isLoading || providersQuery.isFetching;
  const shouldShowActionError = actionData?.error && navigation.state === "idle";

  return (
    <div className="mx-auto flex min-h-screen flex-col justify-center bg-slate-50 px-6 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-10 shadow-soft">
        <header className="space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Welcome back</p>
          <h1 className="text-3xl font-semibold text-slate-900">Sign in to ADE</h1>
          <p className="text-sm text-slate-600">
            Enter your email and password or continue with a connected provider.
          </p>
        </header>

        {providersError ? <Alert tone="warning" className="mt-6">{providersError}</Alert> : null}

        {isProvidersLoading ? (
          <div className="mt-6 space-y-3">
            <div className="h-10 animate-pulse rounded-lg bg-slate-100" />
            <div className="h-10 animate-pulse rounded-lg bg-slate-100" />
          </div>
        ) : providers.length > 0 ? (
          <div className="mt-6 space-y-3">
            {providers.map((provider) => (
              <a
                key={provider.id}
                href={provider.start_url}
                className="flex w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
              >
                Continue with {provider.label}
              </a>
            ))}
          </div>
        ) : null}

        {!forceSso ? (
          <Form method="post" className="mt-8 space-y-6" replace>
            <input type="hidden" name="redirectTo" value={redirectTo} />
            <FormField label="Email address" required>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                name="email"
              />
            </FormField>

            <FormField label="Password" required>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                name="password"
              />
            </FormField>

            {shouldShowActionError ? <Alert tone="danger">{actionData.error}</Alert> : null}

            <Button type="submit" className="w-full justify-center" isLoading={isSubmitting}>
              {isSubmitting ? "Signing in…" : "Continue"}
            </Button>
          </Form>
        ) : (
          <Alert tone="info" className="mt-8">
            Password sign-in is disabled for this deployment. Use one of the configured providers above.
          </Alert>
        )}
      </div>
    </div>
  );
}

export function clientShouldRevalidate(_: ShouldRevalidateFunctionArgs) {
  return false;
}

interface LoginActionError {
  readonly error: string;
}
