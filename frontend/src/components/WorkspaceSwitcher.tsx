import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useWorkspacesQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";

export function WorkspaceSwitcher() {
  const navigate = useNavigate();
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();
  const { data: workspaces = [], isLoading } = useWorkspacesQuery();

  const options = useMemo(
    () =>
      workspaces.map((workspace) => ({
        id: workspace.workspace_id,
        name: workspace.name,
      })),
    [workspaces],
  );

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const nextId = event.target.value || null;
    setSelectedWorkspaceId(nextId);
    if (nextId) {
      navigate(`/workspaces/${nextId}/overview`);
    }
  };

  return (
    <label className="workspace-switcher">
      <span className="muted">Workspace</span>
      <select
        className="workspace-select"
        value={selectedWorkspaceId ?? ""}
        onChange={handleChange}
        disabled={isLoading || options.length === 0}
      >
        <option value="" disabled>
          {isLoading ? "Loading…" : "Select a workspace"}
        </option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}
