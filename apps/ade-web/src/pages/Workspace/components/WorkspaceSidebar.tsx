import { NavLink, useLocation } from "react-router-dom";
import { FileText, PlayCircle, Settings, Wrench } from "lucide-react";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";

export function WorkspaceSidebar() {
  const { workspace } = useWorkspaceContext();
  const { pathname } = useLocation();

  const base = `/workspaces/${workspace.id}`;

  const links = {
    documents: `${base}/documents`,
    runs: `${base}/runs`,
    configBuilder: `${base}/config-builder`,
    settings: `${base}/settings`,
  } as const;

  const isActive = (link: string) => pathname === link || pathname.startsWith(`${link}/`);

  return (
    <Sidebar collapsible="icon">
      <SidebarTrigger />
      <SidebarHeader>
        <div>Workspace switcher</div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.documents)}>
                  <NavLink to={links.documents}>
                    <FileText />
                    <span>Documents</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.runs)}>
                  <NavLink to={links.runs}>
                    <PlayCircle />
                    <span>Runs</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.configBuilder)}>
                  <NavLink to={links.configBuilder}>
                    <Wrench />
                    <span>Config Builder</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.settings)}>
                  <NavLink to={links.settings}>
                    <Settings />
                    <span>Workspace Settings</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
