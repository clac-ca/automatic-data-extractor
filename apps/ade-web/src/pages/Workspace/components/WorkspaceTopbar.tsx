import { Link } from "react-router-dom";

import {
  Topbar,
  TopbarBrand,
  TopbarContent,
  TopbarEnd,
  TopbarStart,
} from "@/components/ui/topbar";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";

export function WorkspaceTopbar() {
  const { workspace } = useWorkspaceContext();

  return (
    <Topbar>
      <TopbarContent>
        <TopbarStart>
          <TopbarBrand asChild>
            <Link to={`/workspaces/${workspace.id}`}>
              <span>{workspace.name || "Workspace"}</span>
            </Link>
          </TopbarBrand>
        </TopbarStart>
        <TopbarEnd />
      </TopbarContent>
    </Topbar>
  );
}
