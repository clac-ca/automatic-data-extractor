import type { ReactNode } from "react"

import { SidebarProvider } from "@/components/ui/sidebar"
import { TopbarProvider } from "@/components/ui/topbar"
import { WorkspaceSidebar } from "@/pages/Workspace/components/WorkspaceSidebar"
import { WorkspaceTopbar } from "@/pages/Workspace/components/WorkspaceTopbar"

export function WorkspaceLayout({ children }: { readonly children: ReactNode }) {
  return (
    <SidebarProvider className="flex h-svh w-full overflow-hidden">
      {/* Column 1: pinned sidebar */}
      <WorkspaceSidebar />

      {/* Column 2: main surface (topbar + scroll area) */}
      <TopbarProvider className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden w-0">
        {/* Row 1 (within main surface): header that never scrolls */}
        <WorkspaceTopbar />

        {/* Row 2: the ONLY scroller */}
        <main className="min-h-0 min-w-0 flex-1 overflow-auto">
          {children}
        </main>
      </TopbarProvider>
    </SidebarProvider>
  )
}
