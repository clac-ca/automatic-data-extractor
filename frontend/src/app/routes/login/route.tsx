import clsx from "clsx";
import { Navigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useSessionQuery } from "@features/auth/hooks/useSessionQuery";
import { useLoginMutation } from "@features/auth/hooks/useLoginMutation";
import { useAuthProviders } from "@features/auth/hooks/useAuthProviders";
import { useSetupStatusQuery } from "@features/setup/hooks/useSetupStatusQuery";
import type { AuthProvider } from "@shared/types/auth";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Enter your email address.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginRoute() {
  const { session } = useSessionQuery({ enabled: false });
  const setupStatusQuery = useSetupStatusQuery({ enabled: !session });
  const providersQuery = useAuthProviders();

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
    clearErrors,
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const loginMutation = useLoginMutation({
    onSuccess() {
      clearErrors("root");
    },
  });

  if (session) {
    return <Navigate to="/" replace />;
  }

  if (setupStatusQuery.data?.requires_setup) {
    return <Navigate to="/setup" replace />;
  }

  const providers = providersQuery.data?.providers ?? [];
  const forceSso = providersQuery.data?.force_sso ?? false;

  return (
    <div className="mx-auto flex min-h-screen flex-col justify-center bg-slate-50 px-6 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-10 shadow-soft">
        <header className="space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            Welcome back
          </p>
          <h1 className="text-3xl font-semibold text-slate-900">Sign in to ADE</h1>
          <p className="text-sm text-slate-600">
            Enter your email and password or continue with a connected provider.
          </p>
        </header>

        {providersQuery.isError ? (
          <Alert tone="warning" className="mt-6">
            We couldn&apos;t load the list of providers. Refresh the page or continue with email.
          </Alert>
        ) : null}

        {providers.length > 0 ? (
          <div className="mt-6 space-y-3">
            {providers.map((provider: AuthProvider) => (
              <a
                key={provider.id}
                href={provider.start_url}
                className={clsx(
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                  "flex w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50",
                )}
              >
                Continue with {provider.label}
              </a>
            ))}
          </div>
        ) : null}

        {!forceSso ? (
          <form
            className="mt-8 space-y-6"
            onSubmit={handleSubmit((values) => {
              clearErrors("root");
              loginMutation.mutate(values, {
                onError(error: unknown) {
                  setError("root", {
                    type: "server",
                    message: error instanceof Error ? error.message : "Unable to sign in.",
                  });
                },
              });
            })}
          >
            <FormField label="Email address" required error={errors.email?.message}>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                {...register("email")}
                invalid={Boolean(errors.email)}
              />
            </FormField>

            <FormField label="Password" required error={errors.password?.message}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                {...register("password")}
                invalid={Boolean(errors.password)}
              />
            </FormField>

            {errors.root ? <Alert tone="danger">{errors.root.message}</Alert> : null}

            <Button type="submit" className="w-full justify-center" isLoading={loginMutation.isPending}>
              {loginMutation.isPending ? "Signing in…" : "Continue"}
            </Button>
          </form>
        ) : (
          <Alert tone="info" className="mt-8">
            Password sign-in is disabled for this deployment. Use one of the configured providers above.
          </Alert>
        )}
      </div>
    </div>
  );
}
