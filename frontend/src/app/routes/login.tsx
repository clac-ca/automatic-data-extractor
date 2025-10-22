import { Form, redirect, useActionData, useNavigation } from "react-router";
import type { ClientActionFunctionArgs, ClientLoaderFunctionArgs, ShouldRevalidateFunctionArgs } from "react-router";
import { z } from "zod";

import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";
import { useAuthProvidersQuery } from "@shared/auth/hooks/useAuthProvidersQuery";
import type { components } from "@openapi";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Enter your email address.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type SessionEnvelope = components["schemas"]["SessionEnvelope"];
type SetupStatus = components["schemas"]["SetupStatus"];

interface LoginActionError {
  readonly error: string;
}

export async function clientLoader({ request }: ClientLoaderFunctionArgs): Promise<null> {
  const url = new URL(request.url);
  const skipSessionCheck = url.searchParams.get("skip_session_check") === "1";
  const skipSetupCheck = url.searchParams.get("skip_setup_check") === "1";
  const requestedNext = url.searchParams.get("next") ?? "/";

  if (!skipSessionCheck) {
    try {
      const sessionResponse = await client.GET("/api/v1/auth/session", { signal: request.signal });
      const session = (sessionResponse.data as SessionEnvelope | null | undefined) ?? null;
      if (session) {
        const destination = session.return_to ?? requestedNext;
        throw redirect(destination);
      }
    } catch (error) {
      if (!(error instanceof ApiError && (error.status === 401 || error.status === 403))) {
        throw error;
      }
    }
  }

  let setupStatus: SetupStatus | null = null;

  if (!skipSetupCheck) {
    const setupResponse = await client.GET("/api/v1/setup/status", { signal: request.signal });
    setupStatus = (setupResponse.data as SetupStatus | null | undefined) ?? null;

    if (setupStatus?.requires_setup) {
      throw redirect("/setup");
    }
  }

  return null;
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
  const url = new URL(request.url);
  const next = url.searchParams.get("next") ?? "/";

  try {
    const response = await client.POST("/api/v1/auth/session", {
      body: { email, password },
    });

    const session = (response.data as SessionEnvelope | null | undefined) ?? null;
    const destination = session?.return_to ?? next;
    throw redirect(destination);
  } catch (error) {
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
