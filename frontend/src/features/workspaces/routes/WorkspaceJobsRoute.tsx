import { useOutletContext } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";
import { RBAC } from "../../../shared/rbac/permissions";
import { hasPermission } from "../../../shared/rbac/utils";

export function WorkspaceJobsRoute() {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace to review job history.
      </div>
    );
  }

  const canRetry = hasPermission(workspace.permissions, RBAC.Workspace.Jobs.ReadWrite);

  return (
    <div className="space-y-6">
      <section className="rounded border border-slate-800 bg-slate-900/60 p-6">
        <h2 className="text-lg font-semibold text-slate-100">Extraction jobs</h2>
        <p className="mt-2 text-sm text-slate-300">
          Job activity and retry controls will appear here once the orchestration endpoints are exposed.
        </p>
        {canRetry ? (
          <p className="mt-4 text-xs text-slate-400">
            You will be able to restart or cancel jobs once queue integration lands.
          </p>
        ) : (
          <p className="mt-4 text-xs text-slate-500">
            Retrying jobs requires Workspace.Jobs.ReadWrite permissions.
          </p>
        )}
      </section>
    </div>
  );
}
