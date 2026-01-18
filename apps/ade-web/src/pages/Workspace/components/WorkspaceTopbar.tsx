import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Topbar,
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
        <TopbarEnd />
      </TopbarContent>
    </Topbar>
  );
}
