import type { ChangeEvent, FormEvent } from "react";
import { useState } from "react";
import { Navigate } from "react-router-dom";

import { useSetupStatusQuery } from "../../features/setup/hooks/useSetupStatusQuery";
import { useCompleteSetupMutation } from "../../features/setup/hooks/useCompleteSetupMutation";
import type { SetupPayload } from "../../shared/types/auth";
import { Alert, Button, FormField, Input } from "../../ui";
import { PageState } from "../components/PageState";

interface SetupFormState {
  displayName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export function SetupRoute() {
  const statusQuery = useSetupStatusQuery();
  const completeSetup = useCompleteSetupMutation();

  const [form, setForm] = useState<SetupFormState>({
    displayName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [formError, setFormError] = useState<string | null>(null);

  if (statusQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Checking setup status" variant="loading" />
      </div>
    );
  }

  if (statusQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState
          title="Unable to determine setup status"
          description="Refresh the page or contact support if the issue persists."
          variant="error"
          action={
            <Button variant="secondary" onClick={() => statusQuery.refetch()}>
              Try again
            </Button>
          }
        />
      </div>
    );
  }

  const status = statusQuery.data;

  if (!status || !status.requires_setup) {
    return <Navigate to="/login" replace />;
  }

  function handleChange<K extends keyof SetupFormState>(key: K) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setForm((current) => ({ ...current, [key]: value }));
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (form.password.trim().length < 12) {
      setFormError("Use at least 12 characters for your password.");
      return;
    }

    if (form.password !== form.confirmPassword) {
      setFormError("Passwords do not match. Check both fields and try again.");
      return;
    }

    const payload: SetupPayload = {
      display_name: form.displayName,
      email: form.email,
      password: form.password,
    };

    completeSetup.mutate(payload, {
      onError(error) {
        setFormError(error instanceof Error ? error.message : "Setup failed. Try again.");
      },
    });
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center bg-slate-50 px-6 py-16">
      <div className="rounded-2xl border border-slate-200 bg-white p-10 shadow-soft">
        <header className="space-y-3 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            First-run configuration
          </p>
          <h1 className="text-3xl font-semibold text-slate-900">Create the first administrator</h1>
          <p className="text-sm text-slate-600">
            Provide the details for the inaugural administrator account. After completion you&apos;ll
            be redirected to the console.
          </p>
        </header>

        {status.force_sso ? (
          <Alert tone="info" className="mt-6">
            This deployment requires single sign-on after the initial administrator is created.
            We&apos;ll prompt you to use your identity provider on the next screen.
          </Alert>
        ) : null}

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="grid gap-6 md:grid-cols-2">
            <FormField label="Display name" required>
              <Input
                id="displayName"
                placeholder="Casey Operator"
                value={form.displayName}
                onChange={handleChange("displayName")}
              />
            </FormField>
            <FormField label="Email" required>
              <Input
                id="email"
                type="email"
                placeholder="casey@example.com"
                value={form.email}
                onChange={handleChange("email")}
              />
            </FormField>
          </div>

          <FormField label="Password" hint="Use at least 12 characters." required>
            <Input
              id="password"
              type="password"
              minLength={12}
              placeholder="••••••••••••"
              value={form.password}
              onChange={handleChange("password")}
            />
          </FormField>

          <FormField label="Confirm password" required>
            <Input
              id="confirmPassword"
              type="password"
              minLength={12}
              placeholder="Re-enter your password"
              value={form.confirmPassword}
              onChange={handleChange("confirmPassword")}
            />
          </FormField>

          {formError ? <Alert tone="danger">{formError}</Alert> : null}

          <div className="flex justify-end">
            <Button type="submit" isLoading={completeSetup.isPending}>
              {completeSetup.isPending ? "Creating administrator…" : "Create administrator"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
