import { type FormEvent, useState } from "react";

import { ApiError } from "../../../shared/api/client";
import { useLoginMutation } from "../hooks/useLoginMutation";
import {
  FormAlert,
  TextField,
  hasFieldErrors,
  parseProblemErrors,
  type FieldErrors,
  validateEmail,
  validatePassword,
} from "../../../shared/forms";

type Provider = { id: string; label: string; icon_url?: string | null; start_url: string };

type LoginFormProps = {
  providers: Provider[];
  forceSso: boolean;
};

const LOGIN_FIELDS = ["email", "password"] as const;
type LoginField = (typeof LOGIN_FIELDS)[number];

function isLoginField(field: string): field is LoginField {
  return LOGIN_FIELDS.includes(field as LoginField);
}

export function LoginForm({ providers, forceSso }: LoginFormProps) {
  const [values, setValues] = useState({ email: "", password: "" });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<LoginField>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const { mutateAsync, isPending } = useLoginMutation();

  const updateField = (field: LoginField, value: string) => {
    setValues((previous) => ({ ...previous, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors: FieldErrors<LoginField> = {};
    const emailError = validateEmail(values.email, {
      requiredMessage: "Enter your email",
      invalidMessage: "Enter a valid email",
    });
    if (emailError) {
      errors.email = emailError;
    }
    const passwordError = validatePassword(values.password);
    if (passwordError) {
      errors.password = passwordError;
    }

    setFieldErrors(errors);
    setAlert(null);

    if (hasFieldErrors(errors)) {
      return;
    }

    try {
      await mutateAsync({ email: values.email.trim(), password: values.password });
    } catch (error) {
      if (error instanceof ApiError) {
        const problemErrors = parseProblemErrors(error.problem);
        const nextErrors: FieldErrors<LoginField> = {};

        for (const [field, message] of Object.entries(problemErrors)) {
          if (isLoginField(field) && message) {
            nextErrors[field] = message;
          }
        }

        setFieldErrors((previous) => ({ ...previous, ...nextErrors }));
        setAlert(error.problem?.detail ?? "Unable to sign in. Try again.");
      } else {
        setAlert("Unable to sign in. Check your connection and try again.");
      }
    }
  };

  if (forceSso) {
    return (
      <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-6">
        <header className="space-y-1 text-center">
          <h2 className="text-xl font-semibold text-slate-50">Single sign-on required</h2>
          <p className="text-sm text-slate-400">Continue with your organisation's identity provider.</p>
        </header>
        <div className="space-y-3">
          {providers.map((provider) => (
            <a
              key={provider.id}
              href={provider.start_url}
              className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm font-medium text-slate-100 hover:border-sky-500"
            >
              <span>Continue with {provider.label}</span>
              {provider.icon_url && <img src={provider.icon_url} alt="" className="h-6 w-6" />}
            </a>
          ))}
        </div>
        <p className="text-xs text-slate-500">Need access? Contact your ADE administrator.</p>
      </section>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow"
      noValidate
    >
      <header className="space-y-1 text-center">
        <h2 className="text-xl font-semibold text-slate-50">Sign in</h2>
        <p className="text-sm text-slate-400">Use your ADE credentials to continue.</p>
      </header>
      <FormAlert message={alert} />
      <TextField
        name="email"
        label="Email"
        type="email"
        autoComplete="email"
        value={values.email}
        onChange={(value) => updateField("email", value)}
        disabled={isPending}
        error={fieldErrors.email}
      />
      <TextField
        name="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        value={values.password}
        onChange={(value) => updateField("password", value)}
        disabled={isPending}
        error={fieldErrors.password}
      />
      <button
        type="submit"
        className="w-full rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400 disabled:opacity-60"
        disabled={isPending}
      >
        {isPending ? "Signing in…" : "Sign in"}
      </button>
      {providers.length > 0 && (
        <div className="space-y-3">
          <div className="text-center text-xs uppercase tracking-wide text-slate-500">or continue with</div>
          <div className="grid gap-3">
            {providers.map((provider) => (
              <a
                key={provider.id}
                href={provider.start_url}
                className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm font-medium text-slate-100 hover:border-sky-500"
              >
                <span>{provider.label}</span>
                {provider.icon_url && <img src={provider.icon_url} alt="" className="h-6 w-6" />}
              </a>
            ))}
          </div>
        </div>
      )}
    </form>
  );
}
