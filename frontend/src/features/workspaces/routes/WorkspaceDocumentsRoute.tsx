import { useOutletContext } from "react-router-dom";

import type { WorkspaceLayoutContext } from "../components/WorkspaceLayout";
import { RBAC } from "../../../shared/rbac/permissions";
import { hasPermission } from "../../../shared/rbac/utils";

export function WorkspaceDocumentsRoute() {
  const { workspace } = useOutletContext<WorkspaceLayoutContext>();

  if (!workspace) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Choose a workspace to view documents.
      </div>
    );
  }

  const canUpload = hasPermission(workspace.permissions, RBAC.Workspace.Documents.ReadWrite);

  return (
    <div className="space-y-6">
      <section className="rounded border border-slate-800 bg-slate-900/60 p-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Documents</h2>
            <p className="text-sm text-slate-300">
              Monitor uploaded files and review extraction status for workspace {workspace.name}.
            </p>
          </div>
          {canUpload ? (
            <button
              type="button"
              className="inline-flex items-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
            >
              Upload document
            </button>
          ) : (
            <span className="text-xs text-slate-500">Upload access requires Workspace.Documents.ReadWrite.</span>
          )}
        </header>
        <p className="mt-6 text-sm text-slate-400">
          Document listings will appear here once the backend endpoints are wired up. For now, this area confirms your access level.
        </p>
      </section>
    </div>
  );
}
