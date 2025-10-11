import type { SessionEnvelope, WorkspaceProfile } from "../../../shared/api/types";
import { useWorkspaceChrome } from "../layout/WorkspaceChromeContext";

interface WorkspaceTopBarProps {
  session: SessionEnvelope | null;
  workspaces: WorkspaceProfile[];
  activeWorkspaceId?: string;
  onSelectWorkspace: (workspaceId: string) => void;
  canCreateWorkspaces: boolean;
  onCreateWorkspace: () => void;
}

export function WorkspaceTopBar({
  session,
  workspaces,
  activeWorkspaceId,
  onSelectWorkspace,
  canCreateWorkspaces,
  onCreateWorkspace,
}: WorkspaceTopBarProps) {
  const { isDesktop, isRailCollapsed, toggleRail, isOverlayOpen } = useWorkspaceChrome();
  const hasWorkspaces = workspaces.length > 0;
  const activeValue = activeWorkspaceId ?? (hasWorkspaces ? workspaces[0]?.id ?? "" : "");

  const toggleLabel = isDesktop
    ? isRailCollapsed
      ? "Expand navigation"
      : "Collapse navigation"
    : isOverlayOpen
    ? "Close navigation"
    : "Open navigation";

  return (
    <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggleRail}
          className="inline-flex h-10 w-10 items-center justify-center rounded border border-slate-800 bg-slate-950 text-slate-200 transition hover:border-slate-700 hover:text-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
          aria-label={toggleLabel}
          aria-expanded={isDesktop ? !isRailCollapsed : isOverlayOpen}
        >
          <span className="sr-only">{toggleLabel}</span>
          <span aria-hidden className="text-lg font-semibold">
            {isDesktop ? (isRailCollapsed ? "»" : "«") : isOverlayOpen ? "×" : "≡"}
          </span>
        </button>
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold uppercase tracking-[0.32em] text-sky-300">ADE</span>
          <span className="hidden text-sm font-medium text-slate-400 sm:block">Automatic Data Extractor</span>
        </div>
        <div className="flex items-center gap-2">
          {hasWorkspaces ? (
            <>
              <label
                htmlFor="workspace-selector"
                className="text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                Workspace
              </label>
              <select
                id="workspace-selector"
                name="workspace"
                className="rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
                value={activeValue}
                onChange={(event) => {
                  const nextWorkspaceId = event.target.value;
                  if (nextWorkspaceId) {
                    onSelectWorkspace(nextWorkspaceId);
                  }
                }}
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </>
          ) : (
            <>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Workspace</span>
              <span className="text-sm text-slate-500">No workspaces yet</span>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 sm:gap-4">
        {canCreateWorkspaces ? (
          <button
            type="button"
            onClick={onCreateWorkspace}
            className="inline-flex items-center rounded border border-sky-500 bg-sky-500/10 px-3 py-2 text-sm font-semibold text-sky-200 transition hover:bg-sky-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
          >
            + New workspace
          </button>
        ) : null}
        <div className="hidden text-right text-sm sm:block">
          <p className="font-medium text-slate-100">{session?.user.display_name ?? session?.user.email ?? ""}</p>
          <p className="text-xs text-slate-500">{session?.user.email ?? ""}</p>
        </div>
        <a
          href="/logout"
          className="rounded border border-transparent px-3 py-2 text-sm font-medium text-slate-300 transition hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
        >
          Sign out
        </a>
      </div>
    </div>
  );
}
