import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
  TopbarContent,
  TopbarEnd,
  TopbarStart,
} from "@/components/ui/topbar";
import { WorkspaceTopbarControls } from "@/pages/Workspace/components/WorkspaceTopbarControls";

export function WorkspaceTopbar() {
  return (
    <Topbar>
      <TopbarContent>
        <TopbarStart>
          <SidebarTrigger className="md:hidden" />
        </TopbarStart>
        <TopbarEnd>
          <WorkspaceTopbarControls />
        </TopbarEnd>
      </TopbarContent>
    </Topbar>
  );
}
