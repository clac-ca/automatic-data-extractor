import { LoginForm } from "../components/LoginForm";
import { useAuthProvidersQuery } from "../hooks/useAuthProviders";

export function LoginRoute() {
  const {
    data: providersData,
    isLoading: isLoadingProviders,
    error: providersError,
  } = useAuthProvidersQuery();

  if (isLoadingProviders) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Preparing sign-in…
      </div>
    );
  }

  if (providersError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to load the sign-in options.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
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
