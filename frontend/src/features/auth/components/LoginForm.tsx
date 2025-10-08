import { type FormEvent, useState } from "react";

import { ApiError } from "../../../shared/api/client";
import { useLoginMutation } from "../hooks/useLoginMutation";

type Provider = { id: string; label: string; icon_url?: string | null; start_url: string };

type LoginFormProps = {
  providers: Provider[];
  forceSso: boolean;
};

type FieldErrors = Partial<Record<"email" | "password", string>>;

function validateEmail(value: string) {
  if (!value.trim()) {
    return "Enter your email";
  }

  const pattern = /.+@.+\..+/;
  return pattern.test(value) ? undefined : "Enter a valid email";
}

function validatePassword(value: string) {
  if (!value) {
    return "Enter your password";
  }

  return undefined;
}

export function LoginForm({ providers, forceSso }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [alert, setAlert] = useState<string | null>(null);
  const { mutateAsync, isPending } = useLoginMutation();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors: FieldErrors = {};
    const emailError = validateEmail(email);
    if (emailError) {
      errors.email = emailError;
    }
    const passwordError = validatePassword(password);
    if (passwordError) {
      errors.password = passwordError;
    }

    setFieldErrors(errors);
    setAlert(null);

    if (Object.keys(errors).length > 0) {
      return;
    }

    try {
      await mutateAsync({ email: email.trim(), password });
    } catch (error) {
      if (error instanceof ApiError) {
        const apiErrors = error.problem?.errors ?? {};
        const nextErrors: FieldErrors = {};
        if (apiErrors.email?.length) {
          nextErrors.email = apiErrors.email.join(" ");
        }
        if (apiErrors.password?.length) {
          nextErrors.password = apiErrors.password.join(" ");
        }
        setFieldErrors(nextErrors);
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
      {alert && (
        <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200" role="alert">
          {alert}
        </div>
      )}
      <div className="space-y-1">
        <label htmlFor="email" className="text-sm font-medium text-slate-200">
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={isPending}
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400"
          aria-invalid={fieldErrors.email ? "true" : undefined}
          aria-describedby={fieldErrors.email ? "email-error" : undefined}
        />
        {fieldErrors.email && (
          <p id="email-error" className="text-xs text-rose-300">
            {fieldErrors.email}
          </p>
        )}
      </div>
      <div className="space-y-1">
        <label htmlFor="password" className="text-sm font-medium text-slate-200">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isPending}
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400"
          aria-invalid={fieldErrors.password ? "true" : undefined}
          aria-describedby={fieldErrors.password ? "password-error" : undefined}
        />
        {fieldErrors.password && (
          <p id="password-error" className="text-xs text-rose-300">
            {fieldErrors.password}
          </p>
        )}
      </div>
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
