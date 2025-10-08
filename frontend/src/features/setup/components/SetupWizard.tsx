import { type FormEvent, useState } from "react";

import { ApiError } from "../../../shared/api/client";
import { useCompleteSetupMutation } from "../hooks/useCompleteSetupMutation";

type Step = "welcome" | "form" | "done";

type FieldErrors = Partial<{
  display_name: string;
  email: string;
  password: string;
  confirm_password: string;
}>;

function validate(values: {
  display_name: string;
  email: string;
  password: string;
  confirm_password: string;
}) {
  const errors: FieldErrors = {};

  if (!values.display_name.trim()) {
    errors.display_name = "Provide a display name";
  }

  const emailPattern = /.+@.+\..+/;
  if (!emailPattern.test(values.email.trim())) {
    errors.email = "Enter a valid email";
  }

  if (values.password.length < 12) {
    errors.password = "Password must be at least 12 characters";
  }

  if (!/[A-Z]/.test(values.password) || !/[a-z]/.test(values.password) || !/[0-9]/.test(values.password)) {
    const message = "Include uppercase, lowercase, and numeric characters";
    errors.password = errors.password ? `${errors.password}. ${message}` : message;
  }

  if (values.password !== values.confirm_password) {
    errors.confirm_password = "Passwords must match";
  }

  return errors;
}

export function SetupWizard() {
  const [step, setStep] = useState<Step>("welcome");
  const [formValues, setFormValues] = useState({
    display_name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [alert, setAlert] = useState<string | null>(null);
  const { mutateAsync, isPending } = useCompleteSetupMutation();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors = validate(formValues);
    setFieldErrors(errors);
    setAlert(null);

    if (Object.keys(errors).length > 0) {
      return;
    }

    try {
      await mutateAsync({
        display_name: formValues.display_name.trim(),
        email: formValues.email.trim(),
        password: formValues.password,
      });
      setStep("done");
    } catch (error) {
      if (error instanceof ApiError) {
        const apiErrors = error.problem?.errors ?? {};
        const nextErrors: FieldErrors = {};
        if (apiErrors.display_name?.length) {
          nextErrors.display_name = apiErrors.display_name.join(" ");
        }
        if (apiErrors.email?.length) {
          nextErrors.email = apiErrors.email.join(" ");
        }
        if (apiErrors.password?.length) {
          nextErrors.password = apiErrors.password.join(" ");
        }
        setFieldErrors(nextErrors);
        setAlert(error.problem?.detail ?? "We could not complete setup. Try again.");
      } else {
        setAlert("We could not complete setup. Try again.");
      }
    }
  };

  if (step === "welcome") {
    return (
      <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-center">
        <h2 className="text-2xl font-semibold text-slate-50">Welcome to ADE</h2>
        <p className="text-sm text-slate-400">
          Let's create the inaugural administrator account so you can start extracting documents.
        </p>
        <button
          type="button"
          onClick={() => setStep("form")}
          className="inline-flex items-center justify-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
        >
          Begin setup
        </button>
      </section>
    );
  }

  if (step === "done") {
    return (
      <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-center">
        <h2 className="text-2xl font-semibold text-slate-50">Setup complete</h2>
        <p className="text-sm text-slate-400">We created your administrator account and signed you in.</p>
      </section>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 rounded-xl border border-slate-800 bg-slate-900/60 p-6"
      noValidate
    >
      <header className="space-y-1 text-center">
        <h2 className="text-xl font-semibold text-slate-50">Administrator account</h2>
        <p className="text-sm text-slate-400">Provide credentials for the inaugural administrator.</p>
      </header>
      {alert && (
        <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200" role="alert">
          {alert}
        </div>
      )}
      <div className="space-y-1">
        <label htmlFor="display_name" className="text-sm font-medium text-slate-200">
          Display name
        </label>
        <input
          id="display_name"
          name="display_name"
          value={formValues.display_name}
          onChange={(event) => setFormValues((prev) => ({ ...prev, display_name: event.target.value }))}
          disabled={isPending}
          autoComplete="name"
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400"
          aria-invalid={fieldErrors.display_name ? "true" : undefined}
          aria-describedby={fieldErrors.display_name ? "display-name-error" : undefined}
        />
        {fieldErrors.display_name && (
          <p id="display-name-error" className="text-xs text-rose-300">
            {fieldErrors.display_name}
          </p>
        )}
      </div>
      <div className="space-y-1">
        <label htmlFor="email" className="text-sm font-medium text-slate-200">
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          value={formValues.email}
          onChange={(event) => setFormValues((prev) => ({ ...prev, email: event.target.value }))}
          disabled={isPending}
          autoComplete="email"
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
          value={formValues.password}
          onChange={(event) => setFormValues((prev) => ({ ...prev, password: event.target.value }))}
          disabled={isPending}
          autoComplete="new-password"
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400"
          aria-invalid={fieldErrors.password ? "true" : undefined}
          aria-describedby={fieldErrors.password ? "password-error" : undefined}
        />
        {fieldErrors.password && (
          <p id="password-error" className="text-xs text-rose-300">
            {fieldErrors.password}
          </p>
        )}
        <p className="text-xs text-slate-500">Use at least 12 characters, including upper and lower case letters and a number.</p>
      </div>
      <div className="space-y-1">
        <label htmlFor="confirm_password" className="text-sm font-medium text-slate-200">
          Confirm password
        </label>
        <input
          id="confirm_password"
          name="confirm_password"
          type="password"
          value={formValues.confirm_password}
          onChange={(event) => setFormValues((prev) => ({ ...prev, confirm_password: event.target.value }))}
          disabled={isPending}
          autoComplete="new-password"
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400"
          aria-invalid={fieldErrors.confirm_password ? "true" : undefined}
          aria-describedby={fieldErrors.confirm_password ? "confirm-password-error" : undefined}
        />
        {fieldErrors.confirm_password && (
          <p id="confirm-password-error" className="text-xs text-rose-300">
            {fieldErrors.confirm_password}
          </p>
        )}
      </div>
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="rounded border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800"
          onClick={() => setStep("welcome")}
          disabled={isPending}
        >
          Back
        </button>
        <button
          type="submit"
          className="rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400 disabled:opacity-60"
          disabled={isPending}
        >
          {isPending ? "Creating…" : "Create administrator"}
        </button>
      </div>
    </form>
  );
}
