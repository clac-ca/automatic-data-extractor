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
      <TopbarContent maxWidth="full" className="px-4 sm:px-6 lg:px-8">
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
