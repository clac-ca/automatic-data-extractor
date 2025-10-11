import { type FormEvent, useState } from "react";

import { ApiError } from "../../../shared/api/client";
import { useCompleteSetupMutation } from "../hooks/useCompleteSetupMutation";
import {
  FormAlert,
  TextField,
  hasFieldErrors,
  parseProblemErrors,
  type FieldErrors,
  validateConfirmPassword,
  validateEmail,
  validatePassword,
  validateRequired,
} from "../../../shared/forms";

type Step = "welcome" | "form" | "done";

const SETUP_FIELDS = ["display_name", "email", "password", "confirm_password"] as const;
type SetupField = (typeof SETUP_FIELDS)[number];

function isSetupField(field: string): field is SetupField {
  return SETUP_FIELDS.some((candidate) => candidate === field);
}

export function SetupWizard() {
  const [step, setStep] = useState<Step>("welcome");
  const [values, setValues] = useState({
    display_name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<SetupField>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const { mutateAsync, isPending } = useCompleteSetupMutation();

  const updateField = (field: SetupField, value: string) => {
    setValues((previous) => ({ ...previous, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors: FieldErrors<SetupField> = {};

    const displayNameError = validateRequired(values.display_name, "Provide a display name");
    if (displayNameError) {
      errors.display_name = displayNameError;
    }

    const emailError = validateEmail(values.email, {
      requiredMessage: "Enter a valid email",
      invalidMessage: "Enter a valid email",
    });
    if (emailError) {
      errors.email = emailError;
    }

    const passwordError = validatePassword(values.password, {
      requiredMessage: "",
      minLength: 12,
      minLengthMessage: "Password must be at least 12 characters",
      requireComplexity: true,
      complexityMessage: "Include uppercase, lowercase, and numeric characters",
    });
    if (passwordError) {
      errors.password = passwordError;
    }

    const confirmError = validateConfirmPassword(values.password, values.confirm_password);
    if (confirmError) {
      errors.confirm_password = confirmError;
    }

    setFieldErrors(errors);
    setAlert(null);

    if (hasFieldErrors(errors)) {
      return;
    }

    try {
      await mutateAsync({
        display_name: values.display_name.trim(),
        email: values.email.trim(),
        password: values.password,
      });
      setStep("done");
      setFieldErrors({});
      setAlert(null);
    } catch (error) {
      if (error instanceof ApiError) {
        const problemErrors = parseProblemErrors(error.problem);
        const nextErrors: FieldErrors<SetupField> = {};

        for (const [field, message] of Object.entries(problemErrors)) {
          if (isSetupField(field) && message) {
            nextErrors[field] = message;
          }
        }

        setFieldErrors((previous) => ({ ...previous, ...nextErrors }));
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
          onClick={() => {
            setStep("form");
            setAlert(null);
            setFieldErrors({});
          }}
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
    <form onSubmit={handleSubmit} className="space-y-6 rounded-xl border border-slate-800 bg-slate-900/60 p-6" noValidate>
      <header className="space-y-1 text-center">
        <h2 className="text-xl font-semibold text-slate-50">Administrator account</h2>
        <p className="text-sm text-slate-400">Provide credentials for the inaugural administrator.</p>
      </header>
      <FormAlert message={alert} />
      <TextField
        name="display_name"
        label="Display name"
        value={values.display_name}
        onChange={(value) => updateField("display_name", value)}
        disabled={isPending}
        autoComplete="name"
        error={fieldErrors.display_name}
      />
      <TextField
        name="email"
        label="Email"
        type="email"
        value={values.email}
        onChange={(value) => updateField("email", value)}
        disabled={isPending}
        autoComplete="email"
        error={fieldErrors.email}
      />
      <TextField
        name="password"
        label="Password"
        type="password"
        value={values.password}
        onChange={(value) => updateField("password", value)}
        disabled={isPending}
        autoComplete="new-password"
        error={fieldErrors.password}
        description="Use at least 12 characters, including upper and lower case letters and a number."
      />
      <TextField
        name="confirm_password"
        label="Confirm password"
        type="password"
        value={values.confirm_password}
        onChange={(value) => updateField("confirm_password", value)}
        disabled={isPending}
        autoComplete="new-password"
        error={fieldErrors.confirm_password}
      />
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="rounded border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800"
          onClick={() => {
            setStep("welcome");
            setAlert(null);
            setFieldErrors({});
          }}
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
