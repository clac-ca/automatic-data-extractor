import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarStart,
} from "@/components/ui/topbar";
import {
  WorkspaceDocumentsTopbarSearch,
  WorkspaceDocumentsTopbarSearchButton,
} from "@/pages/Workspace/components/WorkspaceDocumentsTopbarSearch";
import { WorkspaceTopbarControls } from "@/pages/Workspace/components/WorkspaceTopbarControls";

export function WorkspaceTopbar() {
  return (
    <Topbar className="shadow-sm">
      <TopbarContent
        maxWidth="full"
        className="px-4 sm:px-6 lg:px-8 md:pl-3 lg:pl-4"
      >
        <TopbarStart className="relative z-10">
          <SidebarTrigger className="h-9 w-9 shrink-0" />
          <WorkspaceDocumentsTopbarSearchButton className="md:hidden" />
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
