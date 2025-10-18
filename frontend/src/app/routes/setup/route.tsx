import { Navigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useSetupStatusQuery } from "../../../features/setup/hooks/useSetupStatusQuery";
import { useCompleteSetupMutation } from "../../../features/setup/hooks/useCompleteSetupMutation";
import { Alert } from "../../../ui/alert";
import { Button } from "../../../ui/button";
import { FormField } from "../../../ui/form-field";
import { Input } from "../../../ui/input";
import { PageState } from "../../../ui/PageState";

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

type SetupFormValues = z.infer<typeof setupSchema>;

export default function SetupRoute() {
  const statusQuery = useSetupStatusQuery();
  const completeSetup = useCompleteSetupMutation();

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
    clearErrors,
  } = useForm<SetupFormValues>({
    resolver: zodResolver(setupSchema),
    defaultValues: {
      displayName: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

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

        <form
          className="mt-8 space-y-6"
          onSubmit={handleSubmit((values) => {
            clearErrors("root");
            completeSetup.mutate(
              {
                display_name: values.displayName,
                email: values.email,
                password: values.password,
              },
              {
                onError(error: unknown) {
                  setError("root", {
                    type: "server",
                    message: error instanceof Error ? error.message : "Setup failed. Try again.",
                  });
                },
              },
            );
          })}
        >
          <div className="grid gap-6 md:grid-cols-2">
            <FormField label="Display name" required error={errors.displayName?.message}>
              <Input
                id="displayName"
                placeholder="Casey Operator"
                {...register("displayName")}
                invalid={Boolean(errors.displayName)}
              />
            </FormField>
            <FormField label="Email" required error={errors.email?.message}>
              <Input
                id="email"
                type="email"
                placeholder="casey@example.com"
                {...register("email")}
                invalid={Boolean(errors.email)}
              />
            </FormField>
          </div>

          <FormField
            label="Password"
            hint="Use at least 12 characters."
            required
            error={errors.password?.message}
          >
            <Input
              id="password"
              type="password"
              minLength={12}
              placeholder="••••••••••••"
              {...register("password")}
              invalid={Boolean(errors.password)}
            />
          </FormField>

          <FormField label="Confirm password" required error={errors.confirmPassword?.message}>
            <Input
              id="confirmPassword"
              type="password"
              minLength={12}
              placeholder="Re-enter your password"
              {...register("confirmPassword")}
              invalid={Boolean(errors.confirmPassword)}
            />
          </FormField>

          {errors.root ? <Alert tone="danger">{errors.root.message}</Alert> : null}

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
