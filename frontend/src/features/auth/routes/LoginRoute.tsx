import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { LoginForm } from "../components/LoginForm";
import { useAuthProvidersQuery } from "../hooks/useAuthProviders";
import { useOptionalSession } from "../hooks/useOptionalSession";
import { useSetupStatusQuery } from "../../setup/hooks/useSetupStatusQuery";

export function LoginRoute() {
  const navigate = useNavigate();
  const {
    data: providersData,
    isLoading: isLoadingProviders,
    error: providersError,
  } = useAuthProvidersQuery();
  const {
    data: setupStatus,
    isLoading: isLoadingSetup,
    error: setupError,
  } = useSetupStatusQuery();
  const { data: session, isLoading: isLoadingSession } = useOptionalSession();

  useEffect(() => {
    if (setupStatus?.requires_setup) {
      navigate("/setup", { replace: true });
    }
  }, [setupStatus, navigate]);

  useEffect(() => {
    if (session) {
      const preferredWorkspace = session.user.preferred_workspace_id ?? undefined;
      const fallback = preferredWorkspace ? `/workspaces/${preferredWorkspace}` : "/workspaces";
      const target = session.return_to ?? fallback;
      navigate(target, { replace: true });
    }
  }, [session, navigate]);

  if (isLoadingProviders || isLoadingSetup || isLoadingSession) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Preparing sign-in…
      </div>
    );
  }

  if (setupError || providersError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to load the sign-in options.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
  }

  if (setupStatus?.requires_setup || session) {
    return null;
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-10 px-6 py-16">
      <div className="space-y-3 text-center">
        <h1 className="text-3xl font-semibold text-slate-50">Sign in to ADE</h1>
        <p className="text-sm text-slate-400">
          Manage workspaces, monitor document extraction, and review configuration history.
        </p>
      </div>
      <LoginForm providers={providersData?.providers ?? []} forceSso={providersData?.force_sso ?? false} />
    </div>
  );
}
