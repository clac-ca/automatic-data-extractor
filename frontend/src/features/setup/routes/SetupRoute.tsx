import { useOutletContext } from "react-router-dom";

import { SetupWizard } from "../components/SetupWizard";
import type { SetupStatusResponse } from "../../../shared/api/types";

export function SetupRoute() {
  const setupStatus = useOutletContext<SetupStatusResponse>();

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-8 px-6 py-16">
      <div className="space-y-3 text-center">
        <h1 className="text-3xl font-semibold text-slate-50">Finish ADE setup</h1>
        <p className="text-sm text-slate-400">
          Provide the inaugural administrator account. After setup, the standard login flow becomes available.
        </p>
      </div>
      {setupStatus.force_sso && (
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
