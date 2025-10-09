import { useOutletContext } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";
import { RBAC } from "../../../shared/rbac/permissions";
import { hasPermission } from "../../../shared/rbac/utils";

export function WorkspaceSettingsRoute() {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace to manage settings.
      </div>
    );
  }

  const canDeleteWorkspace = hasPermission(workspace.permissions, RBAC.Workspace.Delete);

  return (
    <div className="space-y-6">
      <section className="rounded border border-slate-800 bg-slate-900/60 p-6">
        <h2 className="text-lg font-semibold text-slate-100">General settings</h2>
        <p className="mt-2 text-sm text-slate-300">
          Workspace rename, slug management, and configuration controls will appear here once write APIs are available.
        </p>
      </section>
      <section className="rounded border border-rose-500/40 bg-rose-500/10 p-6">
        <h3 className="text-lg font-semibold text-rose-100">Danger zone</h3>
        <p className="mt-2 text-sm text-rose-100/80">
          Deleting a workspace permanently removes documents, jobs, and configuration history.
        </p>
        {canDeleteWorkspace ? (
          <button
            type="button"
            disabled
            className="mt-4 inline-flex items-center rounded border border-rose-500/60 bg-rose-500/20 px-4 py-2 text-sm font-semibold text-rose-100 opacity-70"
            title="Workspace deletion will be wired up when the backend endpoint is ready."
          >
            Delete workspace
          </button>
        ) : (
          <p className="mt-4 text-xs text-rose-200/80">Workspace.Delete permission is required to remove this workspace.</p>
        )}
      </section>
    </div>
  );
}
