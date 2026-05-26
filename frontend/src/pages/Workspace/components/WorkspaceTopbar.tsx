import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { UnifiedTopbarControls } from "@/app/layouts/components/topbar/UnifiedTopbarControls";
import {
  WorkspaceDocumentsTopbarSearch,
  WorkspaceDocumentsTopbarSearchButton,
} from "@/pages/Workspace/components/WorkspaceDocumentsTopbarSearch";

export function WorkspaceTopbar() {
  return (
    <header
      data-slot="topbar"
      className="flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4 text-foreground shadow-sm sm:px-6 lg:px-8 md:pl-3 lg:pl-4"
    >
      <SidebarTrigger className="size-8" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <WorkspaceDocumentsTopbarSearchButton className="md:hidden" />
      <div className="hidden min-w-0 flex-1 justify-center md:flex">
        <WorkspaceDocumentsTopbarSearch className="w-full max-w-xl" />
      </div>
      <div className="ml-auto flex items-center">
        <UnifiedTopbarControls />
      </div>
    </header>
  );
}
