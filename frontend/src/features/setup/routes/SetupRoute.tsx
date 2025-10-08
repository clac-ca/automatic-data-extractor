import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { SetupWizard } from "../components/SetupWizard";
import { useSetupStatusQuery } from "../hooks/useSetupStatusQuery";

export function SetupRoute() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useSetupStatusQuery();

  useEffect(() => {
    if (data && !data.requires_setup) {
      navigate("/login", { replace: true });
    }
  }, [data, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Checking setup status…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We could not load setup status.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
  }

  if (!data?.requires_setup) {
    return null;
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-8 px-6 py-16">
      <div className="space-y-3 text-center">
        <h1 className="text-3xl font-semibold text-slate-50">Finish ADE setup</h1>
        <p className="text-sm text-slate-400">
          Provide the inaugural administrator account. After setup, the standard login flow becomes available.
        </p>
      </div>
      {data.force_sso && (
        <div className="rounded border border-sky-500/40 bg-sky-500/10 px-4 py-3 text-sm text-sky-100" role="status">
          <p className="font-medium">Single sign-on required after setup</p>
          <p className="mt-1 text-sky-200/80">
            Your organisation enforces SSO for all users. We will create a break-glass administrator that can sign in with
            credentials before SSO is enabled.
          </p>
        </div>
      )}
      <SetupWizard />
    </div>
  );
}
