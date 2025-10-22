import { Form, redirect, useActionData, useLoaderData, useNavigation } from "react-router";
import type { ClientActionFunctionArgs, ClientLoaderFunctionArgs } from "react-router";
import { z } from "zod";

import { ApiError } from "@shared/api";
import {
  DEFAULT_APP_HOME,
  buildLoginRedirect,
  chooseDestination,
  sanitizeNextPath,
} from "@shared/auth/utils/authNavigation";
import { completeSetup, fetchSetupStatus, type SetupStatus } from "@shared/setup/api";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";

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

interface SetupLoaderData {
  readonly forceSso: boolean;
  readonly redirectTo: string;
}

interface SetupActionError {
  readonly error: string;
}

export async function clientLoader({
  request,
}: ClientLoaderFunctionArgs): Promise<SetupLoaderData> {
  const url = new URL(request.url);
  const redirectTo =
    sanitizeNextPath(url.searchParams.get("redirectTo")) ?? DEFAULT_APP_HOME;
  const status = await fetchSetupStatus({ signal: request.signal });

  if (!status?.requires_setup) {
    throw redirect(buildLoginRedirect(redirectTo));
  }

  return { forceSso: Boolean(status.force_sso), redirectTo };
}

export async function clientAction({ request }: ClientActionFunctionArgs) {
  const formData = await request.formData();
  const raw = Object.fromEntries(formData);
  const parsed = setupSchema.safeParse(raw);

  if (!parsed.success) {
    const message = parsed.error.issues[0]?.message ?? "Invalid input.";
    return { error: message };
  }

  const redirectTo =
    sanitizeNextPath(typeof raw.redirectTo === "string" ? raw.redirectTo : null) ?? DEFAULT_APP_HOME;
  const { displayName, email, password } = parsed.data;

  try {
    const session = await completeSetup({
      display_name: displayName,
      email,
      password,
    });
    throw redirect(chooseDestination(session.return_to, redirectTo));
  } catch (error: unknown) {
    if (error instanceof Response) {
      throw error;
    }
    if (error instanceof ApiError) {
      const message = error.problem?.detail ?? error.message ?? "Setup failed. Try again.";
      return { error: message };
    }
    if (error instanceof Error) {
      return { error: error.message };
    }
    return { error: "Setup failed. Try again." };
  }
}

export default function SetupRoute() {
  const { forceSso, redirectTo } = useLoaderData<SetupLoaderData>();
  const actionData = useActionData<SetupActionError | undefined>();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center bg-slate-50 px-6 py-16">
      <div className="rounded-2xl border border-slate-200 bg-white p-10 shadow-soft">
        <header className="space-y-3 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            First-run configuration
          </p>
          <h1 className="text-3xl font-semibold text-slate-900">Create the first administrator</h1>
          <p className="text-sm text-slate-600">
            Provide credentials for the inaugural administrator account. We'll redirect after
            completion.
          </p>
        </header>

        {forceSso ? (
          <Alert tone="info" className="mt-6">
            This deployment enforces single sign-on after the initial administrator is created.
          </Alert>
        ) : null}

        <Form method="post" className="mt-8 space-y-6" replace>
          <input type="hidden" name="redirectTo" value={redirectTo} />
          <div className="grid gap-6 md:grid-cols-2">
            <FormField label="Display name" required>
              <Input
                id="displayName"
                name="displayName"
                placeholder="Casey Operator"
                required
              />
            </FormField>
            <FormField label="Email" required>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="casey@example.com"
                required
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
            />
          </FormField>

          {actionData?.error ? <Alert tone="danger">{actionData.error}</Alert> : null}

          <div className="flex justify-end">
            <Button type="submit" isLoading={isSubmitting}>
              {isSubmitting ? "Creating administrator…" : "Create administrator"}
            </Button>
          </div>
        </Form>
      </div>
    </div>
  );
}
