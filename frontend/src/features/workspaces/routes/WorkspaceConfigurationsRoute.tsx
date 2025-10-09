import { useOutletContext } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";
import { RBAC } from "../../../shared/rbac/permissions";
import { hasPermission } from "../../../shared/rbac/utils";

export function WorkspaceConfigurationsRoute() {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace to view configuration history.
      </div>
    );
  }

  const canManage = hasPermission(workspace.permissions, RBAC.Workspace.Configurations.ReadWrite);

  return (
    <div className="space-y-6">
      <section className="rounded border border-slate-800 bg-slate-900/60 p-6">
        <h2 className="text-lg font-semibold text-slate-100">Configurations</h2>
        <p className="mt-2 text-sm text-slate-300">
          Active and draft configurations will surface here once configuration APIs are available.
        </p>
        {canManage ? (
          <p className="mt-4 text-xs text-slate-400">
            You'll be able to publish revisions and manage drafts when write APIs are deployed.
          </p>
        ) : (
          <p className="mt-4 text-xs text-slate-500">
            Managing configurations requires Workspace.Configurations.ReadWrite permissions.
          </p>
        )}
      </section>
    </div>
  );
}
