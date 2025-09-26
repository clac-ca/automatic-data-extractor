import type { ChangeEvent } from "react";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useToast } from "@hooks/useToast";
import { useWorkspace } from "@hooks/useWorkspace";

import { useWorkspacesQuery } from "@features/workspaces/hooks/useWorkspacesQuery";

import "@styles/form-controls.css";

export function WorkspaceSwitcher(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const { workspaceId, setWorkspace } = useWorkspace();
  const { data, isLoading, error } = useWorkspacesQuery();
  const { pushToast } = useToast();
  const workspaces = data?.workspaces ?? [];
  const preferredWorkspaceId = data?.defaultWorkspaceId ?? workspaces[0]?.workspaceId ?? null;

  useEffect(() => {
    if (error) {
      pushToast({
        tone: "error",
        title: "Unable to load workspaces",
        description: error.message
      });
    }
  }, [error, pushToast]);

  useEffect(() => {
    if (!preferredWorkspaceId || workspaceId) {
      return;
    }

    if (location.pathname === "/") {
      setWorkspace(preferredWorkspaceId);
      navigate(`/workspaces/${preferredWorkspaceId}/overview`, { replace: true });
    }
  }, [location.pathname, navigate, preferredWorkspaceId, setWorkspace, workspaceId]);

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextWorkspaceId = event.target.value || null;
    setWorkspace(nextWorkspaceId);

    if (nextWorkspaceId) {
      navigate(`/workspaces/${nextWorkspaceId}/overview`);
    } else {
      navigate("/workspaces");
    }
  };

  return (
    <label className="form-control" aria-live="polite">
      <span className="form-control__label">Workspace</span>
      <select
        className="form-control__select"
        value={workspaceId ?? ""}
        onChange={handleChange}
        disabled={isLoading || workspaces.length === 0}
      >
        <option value="">Select workspace</option>
        {workspaces.map((workspace) => (
          <option key={workspace.workspaceId} value={workspace.workspaceId}>
            {workspace.name}
          </option>
        ))}
      </select>
    </label>
  );
}
