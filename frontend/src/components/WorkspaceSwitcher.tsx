import { useEffect, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useWorkspacesQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";

export function WorkspaceSwitcher() {
  const navigate = useNavigate();
  const { data, isLoading } = useWorkspacesQuery();
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();

  useEffect(() => {
    if (!data) {
      return;
    }
    if (data.length === 0) {
      if (selectedWorkspaceId !== null) {
        setSelectedWorkspaceId(null);
      }
      return;
    }

    const exists = data.some((item) => item.workspace_id === selectedWorkspaceId);
    if (exists) {
      return;
    }

    const fallback =
      data.find((item) => item.is_default) ?? data[0] ?? null;
    if (fallback) {
      setSelectedWorkspaceId(fallback.workspace_id);
    }
  }, [data, selectedWorkspaceId, setSelectedWorkspaceId]);

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    setSelectedWorkspaceId(value || null);
    if (value) {
      navigate(`/workspaces/${value}`);
    }
  };

  if (isLoading) {
    return <span className="muted">Loading workspaces…</span>;
  }

  if (!data || data.length === 0) {
    return <span className="muted">No workspaces</span>;
  }

  return (
    <label className="workspace-switcher">
      <span className="sr-only">Switch workspace</span>
      <select value={selectedWorkspaceId ?? ""} onChange={handleChange}>
        {data.map((workspace) => (
          <option key={workspace.workspace_id} value={workspace.workspace_id}>
            {workspace.name}
          </option>
        ))}
      </select>
    </label>
  );
}
