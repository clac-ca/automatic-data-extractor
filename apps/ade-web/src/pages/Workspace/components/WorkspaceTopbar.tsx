import { WorkspaceSearch } from "@/pages/Workspace/components/WorkspaceSearch";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarStart,
} from "@/components/ui/topbar";

export function WorkspaceTopbar() {
  return (
    <Topbar>
      <TopbarContent>
        <TopbarStart>
          <SidebarTrigger className="md:hidden" />
        </TopbarStart>
        <TopbarCenter>
          <div className="w-full max-w-[480px]">
            <WorkspaceSearch />
          </div>
        </TopbarCenter>
        <TopbarEnd />
      </TopbarContent>
    </Topbar>
  );
}
