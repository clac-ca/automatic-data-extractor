import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarStart,
} from "@/components/ui/topbar";
import { WorkspaceDocumentsTopbarSearch } from "@/pages/Workspace/components/WorkspaceDocumentsTopbarSearch";
import { WorkspaceTopbarControls } from "@/pages/Workspace/components/WorkspaceTopbarControls";

export function WorkspaceTopbar() {
  return (
    <Topbar>
      <TopbarContent maxWidth="full" className="px-4 sm:px-6 lg:px-8">
        <TopbarStart>
          <SidebarTrigger className="md:hidden" />
        </TopbarStart>
        <TopbarCenter className="hidden md:flex">
          <WorkspaceDocumentsTopbarSearch className="w-full max-w-xl" />
        </TopbarCenter>
        <TopbarEnd>
          <WorkspaceTopbarControls />
        </TopbarEnd>
      </TopbarContent>
    </Topbar>
  );
}
