import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";

import { RunsTableView } from "./components/table/RunsTableView";

export default function RunsScreen() {
  const { workspace } = useWorkspaceContext();

  return (
    <div className="runs flex min-h-0 flex-1 flex-col bg-background text-foreground">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-6 py-4">
          <RunsTableView workspaceId={workspace.id} />
        </section>
      </div>
    </div>
  );
}
