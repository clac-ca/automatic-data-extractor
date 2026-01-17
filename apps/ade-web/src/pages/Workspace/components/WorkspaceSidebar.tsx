import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, createSearchParams, useLocation, useNavigate } from "react-router-dom";
import { Check, ChevronsUpDown, FileText, LayoutGrid, PlayCircle, Settings, Wrench } from "lucide-react";

import { fetchWorkspaceDocuments, type DocumentChangeEntry, type DocumentPageResult } from "@/api/documents";
import { UploadIcon } from "@/components/icons";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AvatarGroup } from "@/components/ui/avatar-group";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/providers/auth/SessionContext";
import { useWorkspaceDocumentsChanges } from "@/pages/Workspace/context/WorkspaceDocumentsStreamContext";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PresenceParticipant } from "@/types/presence";

const ASSIGNED_DOCUMENTS_LIMIT = 20;
const ASSIGNED_DOCUMENTS_SORT = '[{"id":"updatedAt","desc":true}]';
const ASSIGNED_DOCUMENT_SKELETONS = ["w-36", "w-28", "w-40", "w-32"];

export function WorkspaceSidebar() {
  const session = useSession();
  const queryClient = useQueryClient();
  const { workspace, workspaces } = useWorkspaceContext();
  const presence = useWorkspacePresence();
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const base = `/workspaces/${workspace.id}`;
  const workspaceLabel = workspace.name?.trim() || "Workspace";
  const workspaceSubpath = pathname.split("/").slice(3).join("/");

  const links = {
    documents: `${base}/documents`,
    runs: `${base}/runs`,
    configBuilder: `${base}/config-builder`,
    settings: `${base}/settings`,
  } as const;

  const assignedDocumentsKey = useMemo(
    () => ["sidebar", "assigned-documents", workspace.id, session.user.id],
    [workspace.id, session.user.id],
  );

  const assignedDocumentsQuery = useQuery({
    queryKey: assignedDocumentsKey,
    queryFn: ({ signal }) =>
      fetchWorkspaceDocuments(
        workspace.id,
        {
          sort: ASSIGNED_DOCUMENTS_SORT,
          limit: ASSIGNED_DOCUMENTS_LIMIT,
          filters: [{ id: "assigneeId", operator: "eq", value: session.user.id }],
        },
        signal,
      ),
    enabled: Boolean(workspace.id && session.user?.id),
    staleTime: 30_000,
  });

  const assignedDocuments = assignedDocumentsQuery.data?.items ?? [];
  const activeDocId = useMemo(() => new URLSearchParams(search).get("docId"), [search]);
  const workspaceParticipants = useMemo(
    () => dedupeParticipants(presence.participants),
    [presence.participants],
  );
  const documentsParticipants = useMemo(
    () => filterParticipantsByPage(presence.participants, "documents"),
    [presence.participants],
  );
  const documentsPresenceById = useMemo(
    () => mapPresenceByDocument(documentsParticipants),
    [documentsParticipants],
  );
  const fallbackAvatar = useMemo(
    () => ({
      id: session.user.id,
      label: session.user.display_name || session.user.email || "You",
      initials: getInitials(session.user.display_name, session.user.email),
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );
  const workspaceAvatarItems = useMemo(() => {
    const items = buildAvatarItems(workspaceParticipants);
    if (items.length === 0) return [fallbackAvatar];
    const hasSelf = workspaceParticipants.some(
      (participant) => participant.user_id === session.user.id,
    );
    return hasSelf ? items : [...items, fallbackAvatar];
  }, [fallbackAvatar, session.user.id, workspaceParticipants]);
  const workspacePresenceLabel = useMemo(
    () => workspaceAvatarItems.map((item) => item.label).join(", "),
    [workspaceAvatarItems],
  );

  const isActive = (link: string) => pathname === link || pathname.startsWith(`${link}/`);
  const initials = (value: string) =>
    value
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0])
      .join("")
      .toUpperCase();

  const updateAssignedDocuments = useCallback(
    (change: DocumentChangeEntry) => {
      const userId = session.user?.id;
      if (!userId) return;
      queryClient.setQueryData<DocumentPageResult | undefined>(assignedDocumentsKey, (current) => {
        if (!current) return current;
        const items = current.items ?? [];
        if (change.type === "document.deleted") {
          return {
            ...current,
            items: items.filter((item) => item.id !== change.documentId),
          };
        }
        const row = change.row;
        if (!row) return current;
        const isAssignedToUser = row.assignee?.id === userId;
        const filtered = items.filter((item) => item.id !== change.documentId);
        if (!isAssignedToUser) {
          return {
            ...current,
            items: filtered,
          };
        }
        const nextItems = [...filtered, row].sort(
          (a, b) => (Date.parse(b.updatedAt) || 0) - (Date.parse(a.updatedAt) || 0),
        );
        return {
          ...current,
          items: nextItems.slice(0, ASSIGNED_DOCUMENTS_LIMIT),
        };
      });
    },
    [assignedDocumentsKey, queryClient, session.user?.id],
  );

  useWorkspaceDocumentsChanges(updateAssignedDocuments);

  return (
    <Sidebar collapsible="icon" className="group-data-[collapsible=icon]:z-50">
      <SidebarHeader>
        <div className="flex items-start gap-2">
          <SidebarMenu className="flex-1">
            <SidebarMenuItem>
              <Popover open={switcherOpen} onOpenChange={setSwitcherOpen}>
                <PopoverTrigger asChild>
                  <SidebarMenuButton
                    type="button"
                    size="lg"
                    className="h-auto w-full justify-between bg-sidebar-accent/40"
                    tooltip={workspaceLabel}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="flex size-8 items-center justify-center rounded-md bg-sidebar-accent text-xs font-semibold uppercase text-sidebar-foreground">
                        {initials(workspaceLabel)}
                      </span>
                      <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
                        <span className="block truncate text-sm font-semibold">{workspaceLabel}</span>
                        <span className="block truncate text-xs text-sidebar-foreground/70">
                          {workspace.slug}
                        </span>
                      </span>
                    </span>
                    <ChevronsUpDown className="size-4 opacity-60 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </PopoverTrigger>
                <PopoverContent
                  side="right"
                  align="start"
                  className="w-(--radix-popover-trigger-width) p-0"
                >
                  <Command>
                    <CommandInput placeholder="Search workspaces..." />
                    <CommandList>
                      <CommandEmpty>No workspaces found.</CommandEmpty>
                      <CommandGroup heading="Workspaces">
                        {workspaces.map((item) => (
                          <CommandItem
                            key={item.id}
                            value={`${item.name} ${item.slug}`}
                            onSelect={() => {
                              const nextPath = workspaceSubpath
                                ? `/workspaces/${item.id}/${workspaceSubpath}`
                                : `/workspaces/${item.id}`;
                              navigate(nextPath);
                              setSwitcherOpen(false);
                            }}
                          >
                            <span className="flex size-7 items-center justify-center rounded-md bg-sidebar-accent text-[11px] font-semibold uppercase text-sidebar-foreground">
                              {initials(item.name || "Workspace")}
                            </span>
                            <span className="min-w-0 flex-1 truncate">
                              {item.name || "Workspace"}
                            </span>
                            <Check
                              className={cn(
                                "ml-auto size-4 text-foreground",
                                item.id === workspace.id ? "opacity-100" : "opacity-0",
                              )}
                            />
                          </CommandItem>
                        ))}
                      </CommandGroup>
                      <CommandSeparator />
                      <CommandGroup heading="Actions">
                        <CommandItem
                          value="View all workspaces"
                          onSelect={() => {
                            navigate("/workspaces");
                            setSwitcherOpen(false);
                          }}
                        >
                          <LayoutGrid />
                          <span>View all workspaces</span>
                        </CommandItem>
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </SidebarMenuItem>
          </SidebarMenu>
          <SidebarTrigger
            className="mt-1 shrink-0 transition-transform duration-200 ease-linear group-data-[collapsible=icon]:translate-x-[calc(100%+theme(spacing.4))]"
          />
        </div>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              type="button"
              className="bg-sidebar-accent text-sidebar-foreground border border-sidebar-border/60 shadow-xs hover:bg-sidebar-accent/80 h-8 rounded-md px-3 text-xs gap-2"
              onClick={() => {
                navigate(links.documents, { state: { openUpload: true } });
              }}
              tooltip="Upload documents"
            >
              <UploadIcon />
              <span>Upload</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel asChild>
            <div className="w-full items-center justify-between gap-2">
              <span>Workspace</span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <AvatarGroup size={18} max={3} className="shrink-0">
                    {workspaceAvatarItems.map((item) => (
                      <Avatar key={item.id} aria-hidden="true" title={item.label}>
                        <AvatarFallback className="bg-sidebar-accent text-[8px] font-semibold text-sidebar-foreground">
                          {item.initials}
                        </AvatarFallback>
                      </Avatar>
                    ))}
                  </AvatarGroup>
                </TooltipTrigger>
                <TooltipContent
                  side="right"
                  align="center"
                  className="max-w-[220px] whitespace-pre-line"
                >
                  {workspacePresenceLabel}
                </TooltipContent>
              </Tooltip>
            </div>
          </SidebarGroupLabel>
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
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Your Documents</SidebarGroupLabel>
          <SidebarGroupContent>
            {assignedDocumentsQuery.isLoading ? (
              <SidebarMenu>
                {ASSIGNED_DOCUMENT_SKELETONS.map((width, index) => (
                  <SidebarMenuItem key={`assigned-documents-skeleton-${index}`}>
                    <div className="flex h-8 items-center gap-2 rounded-md px-2">
                      <Skeleton className="size-4 rounded-sm bg-sidebar-accent/70" />
                      <Skeleton className={cn("h-4 bg-sidebar-accent/70", width)} />
                    </div>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            ) : assignedDocumentsQuery.isError ? (
              <p className="px-2 py-2 text-xs text-sidebar-foreground/70">
                Unable to load assigned documents.
              </p>
            ) : assignedDocuments.length === 0 ? (
              <p className="px-2 py-2 text-xs text-sidebar-foreground/70">
                No assigned documents yet.
              </p>
            ) : (
              <SidebarMenu>
                {assignedDocuments.map((document) => {
                  const documentParticipants = documentsPresenceById.get(document.id) ?? [];
                  const documentAvatars = buildAvatarItems(documentParticipants);
                  const documentPresenceLabel = documentAvatars
                    .map((item) => item.label)
                    .join(", ");
                  return (
                    <SidebarMenuItem key={document.id}>
                      <SidebarMenuButton asChild isActive={document.id === activeDocId}>
                        <NavLink
                          to={`${links.documents}?${createSearchParams({
                            docId: document.id,
                            panes: "preview",
                          })}`}
                        >
                          <FileText />
                          <span className="min-w-0 flex-1 truncate">{document.name}</span>
                          {documentAvatars.length > 0 ? (
                            <div className="ml-auto flex items-center group-data-[collapsible=icon]:hidden">
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <AvatarGroup size={18} max={2}>
                                    {documentAvatars.map((item) => (
                                      <Avatar key={item.id} aria-hidden="true" title={item.label}>
                                        <AvatarFallback className="bg-sidebar-accent text-[8px] font-semibold text-sidebar-foreground">
                                          {item.initials}
                                        </AvatarFallback>
                                      </Avatar>
                                    ))}
                                  </AvatarGroup>
                                </TooltipTrigger>
                                <TooltipContent
                                  side="right"
                                  align="center"
                                  className="max-w-[220px] whitespace-pre-line"
                                >
                                  {documentPresenceLabel}
                                </TooltipContent>
                              </Tooltip>
                            </div>
                          ) : null}
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarSeparator />
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild isActive={isActive(links.settings)}>
              <NavLink to={links.settings}>
                <Settings />
                <span>Workspace Settings</span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function getPresencePage(participant: PresenceParticipant) {
  const presence = participant.presence;
  if (!presence || typeof presence !== "object") return null;
  const page = presence["page"];
  return typeof page === "string" ? page : null;
}

function getSelectedDocumentId(participant: PresenceParticipant) {
  const selection = participant.selection;
  if (!selection || typeof selection !== "object") return null;
  const documentId = selection["documentId"];
  return typeof documentId === "string" ? documentId : null;
}

function rankParticipant(participant: PresenceParticipant) {
  let score = 0;
  if (participant.status === "active") score += 2;
  if (getSelectedDocumentId(participant)) score += 3;
  if (participant.editing) score += 1;
  return score;
}

function sortParticipants(participants: PresenceParticipant[]) {
  return participants.sort((a, b) => {
    const aPriority = a.status === "active" ? 0 : 1;
    const bPriority = b.status === "active" ? 0 : 1;
    if (aPriority !== bPriority) return aPriority - bPriority;
    const aLabel = a.display_name || a.email || "Workspace member";
    const bLabel = b.display_name || b.email || "Workspace member";
    return aLabel.localeCompare(bLabel);
  });
}

function dedupeParticipants(participants: PresenceParticipant[]) {
  const byUser = new Map<string, PresenceParticipant>();
  for (const participant of participants) {
    const key = participant.user_id || participant.client_id;
    const existing = byUser.get(key);
    if (!existing || rankParticipant(participant) > rankParticipant(existing)) {
      byUser.set(key, participant);
    }
  }
  return sortParticipants(Array.from(byUser.values()));
}

function filterParticipantsByPage(participants: PresenceParticipant[], page: string) {
  return participants.filter((participant) => getPresencePage(participant) === page);
}

function mapPresenceByDocument(participants: PresenceParticipant[]) {
  const map = new Map<string, Map<string, PresenceParticipant>>();
  participants.forEach((participant) => {
    const documentId = getSelectedDocumentId(participant);
    if (!documentId) return;
    const userKey = participant.user_id || participant.client_id;
    const bucket = map.get(documentId) ?? new Map<string, PresenceParticipant>();
    const existing = bucket.get(userKey);
    if (!existing || rankParticipant(participant) > rankParticipant(existing)) {
      bucket.set(userKey, participant);
    }
    map.set(documentId, bucket);
  });

  const resolved = new Map<string, PresenceParticipant[]>();
  map.forEach((bucket, documentId) => {
    resolved.set(documentId, sortParticipants(Array.from(bucket.values())));
  });
  return resolved;
}

function buildAvatarItems(participants: PresenceParticipant[]) {
  return participants.map((participant) => {
    const name = participant.display_name ?? undefined;
    const email = participant.email ?? undefined;
    return {
      id: participant.user_id || participant.client_id,
      label: name || email || "Workspace member",
      initials: getInitials(name, email),
    };
  });
}
