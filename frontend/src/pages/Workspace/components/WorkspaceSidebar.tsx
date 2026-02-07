import { useCallback, useMemo, useState, type HTMLAttributes } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Check, ChevronDown, ChevronsUpDown, FileText, LayoutGrid, PlayCircle, Plus, Settings, Wrench } from "lucide-react";

import {
  fetchWorkspaceDocuments,
  fetchWorkspaceDocumentRowsByIdFilter,
  type DocumentChangeNotification,
  type DocumentListRow,
  type DocumentPageResult,
} from "@/api/documents";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AvatarGroup } from "@/components/ui/avatar-group";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useSession } from "@/providers/auth/SessionContext";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { partitionDocumentChanges } from "@/pages/Workspace/sections/Documents/shared/documentChanges";
import { useDocumentsDeltaSync } from "@/pages/Workspace/sections/Documents/shared/hooks/useDocumentsDeltaSync";
import { buildDocumentDetailUrl } from "@/pages/Workspace/sections/Documents/shared/navigation";
import {
  Search,
  SearchEmpty,
  SearchGroup,
  SearchInput,
  SearchItem,
  SearchList,
  SearchSeparator,
} from "@/components/ui/search";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PresenceParticipant } from "@/types/presence";
import type { WorkspaceProfile } from "@/types/workspaces";

const ASSIGNED_DOCUMENTS_LIMIT = 20;
const ASSIGNED_DOCUMENTS_SORT = '[{"id":"updatedAt","desc":true}]';
const ASSIGNED_DOCUMENT_SKELETON_COUNT = 4;

type AvatarItem = {
  id: string;
  label: string;
  initials: string;
};

type NavIcon = typeof FileText;

type WorkspaceNavItem = {
  key: "documents" | "runs" | "configBuilder";
  label: string;
  to: string;
  Icon: NavIcon;
};

type WorkspaceSwitcherProps = {
  workspace: WorkspaceProfile;
  workspaces: WorkspaceProfile[];
  workspaceLabel: string;
  onSelectWorkspace: (workspaceId: string) => void;
  onViewAllWorkspaces: () => void;
};

type WorkspaceNavSectionProps = {
  navItems: WorkspaceNavItem[];
  isActive: (link: string) => boolean;
  workspaceAvatarItems: AvatarItem[];
  workspacePresenceLabel: string;
};

type WorkspacePresenceSummaryProps = HTMLAttributes<HTMLDivElement> & {
  items: AvatarItem[];
  label: string;
};

type AssignedDocumentsSectionProps = {
  assignedDocuments: DocumentListRow[];
  documentsPresenceById: Map<string, PresenceParticipant[]>;
  activeDocId: string | null;
  isLoading: boolean;
  isError: boolean;
  onUploadDocuments: () => void;
};

type AssignedDocumentItemProps = {
  document: DocumentListRow;
  documentsPresenceById: Map<string, PresenceParticipant[]>;
  isActive: boolean;
};

export function WorkspaceSidebar() {
  const session = useSession();
  const { canAccessOrganizationSettings } = useGlobalPermissions();
  const queryClient = useQueryClient();
  const { workspace, workspaces } = useWorkspaceContext();
  const presence = useWorkspacePresence();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const base = `/workspaces/${workspace.id}`;
  const workspaceLabel = workspace.name?.trim() || "Workspace";
  const workspaceSubpath = pathname.split("/").slice(3).join("/");

  const links = {
    documents: `${base}/documents`,
    runs: `${base}/runs`,
    configBuilder: `${base}/config-builder`,
    settings: `${base}/settings`,
    organizationSettings: "/organization/settings",
  } as const;

  const navItems = useMemo<WorkspaceNavItem[]>(
    () => [
      { key: "documents", label: "Documents", to: links.documents, Icon: FileText },
      { key: "runs", label: "Runs", to: links.runs, Icon: PlayCircle },
      { key: "configBuilder", label: "Config Builder", to: links.configBuilder, Icon: Wrench },
    ],
    [links.configBuilder, links.documents, links.runs],
  );

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

  const assignedChangesCursor = assignedDocumentsQuery.data?.meta?.changesCursor ?? null;

  const applyAssignedChanges = useCallback(
    async (changes: DocumentChangeNotification[]) => {
      const userId = session.user?.id;
      if (!userId || changes.length === 0) return;
      const { deleteIds, upsertIds } = partitionDocumentChanges(changes);

      let rows: DocumentListRow[] = [];
      if (upsertIds.length > 0) {
        rows = await fetchWorkspaceDocumentRowsByIdFilter(
          workspace.id,
          upsertIds,
          {
            sort: ASSIGNED_DOCUMENTS_SORT,
            filters: [{ id: "assigneeId", operator: "eq", value: userId }],
          },
        );
      }
      const rowsById = new Map(rows.map((row) => [row.id, row]));

      queryClient.setQueryData<DocumentPageResult | undefined>(assignedDocumentsKey, (current) => {
        if (!current) return current;
        const items = current.items ?? [];
        const filtered = items.filter(
          (item) => !deleteIds.includes(item.id) && !upsertIds.includes(item.id),
        );
        const nextItems = [...filtered, ...rowsById.values()].sort(
          (a, b) => (Date.parse(b.updatedAt) || 0) - (Date.parse(a.updatedAt) || 0),
        );
        return {
          ...current,
          items: nextItems.slice(0, ASSIGNED_DOCUMENTS_LIMIT),
        };
      });
    },
    [assignedDocumentsKey, queryClient, session.user?.id, workspace.id],
  );

  useDocumentsDeltaSync({
    workspaceId: workspace.id,
    changesCursor: assignedChangesCursor,
    resetKey: session.user?.id ?? null,
    onApplyChanges: applyAssignedChanges,
    onSnapshotStale: () => {
      void assignedDocumentsQuery.refetch();
    },
  });

  const assignedDocuments = assignedDocumentsQuery.data?.items ?? [];
  const activeDocId = useMemo(() => {
    const prefix = `/workspaces/${workspace.id}/documents/`;
    if (!pathname.startsWith(prefix)) return null;
    const remainder = pathname.slice(prefix.length);
    const segment = remainder.split("/")[0];
    return segment ? decodeURIComponent(segment) : null;
  }, [pathname, workspace.id]);
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

  const handleWorkspaceSelect = useCallback(
    (workspaceId: string) => {
      const nextPath = workspaceSubpath
        ? `/workspaces/${workspaceId}/${workspaceSubpath}`
        : `/workspaces/${workspaceId}`;
      navigate(nextPath);
    },
    [navigate, workspaceSubpath],
  );

  const handleViewAllWorkspaces = useCallback(() => {
    navigate("/workspaces");
  }, [navigate]);

  const handleUploadDocuments = useCallback(() => {
    navigate(links.documents, { state: { openUpload: true } });
  }, [navigate, links.documents]);

  return (
    <Sidebar
      collapsible="icon"
      className="group-data-[collapsible=icon]:z-50 group-data-[side=left]:border-r-0 group-data-[side=right]:border-l-0"
    >
      <SidebarHeader className="relative z-30 h-14 justify-center !p-0 bg-topbar text-topbar-foreground border-b border-topbar-border shadow-sm after:absolute after:-right-4 after:top-0 after:h-full after:w-4 after:bg-topbar after:content-[''] after:pointer-events-none after:z-30">
        <div className="flex items-center">
          <SidebarMenu className="flex-1">
            <SidebarMenuItem>
              <WorkspaceSwitcher
                workspace={workspace}
                workspaces={workspaces}
                workspaceLabel={workspaceLabel}
                onSelectWorkspace={handleWorkspaceSelect}
                onViewAllWorkspaces={handleViewAllWorkspaces}
              />
            </SidebarMenuItem>
          </SidebarMenu>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <WorkspaceNavSection
          navItems={navItems}
          isActive={isActive}
          workspaceAvatarItems={workspaceAvatarItems}
          workspacePresenceLabel={workspacePresenceLabel}
        />
        <AssignedDocumentsSection
          assignedDocuments={assignedDocuments}
          documentsPresenceById={documentsPresenceById}
          activeDocId={activeDocId}
          isLoading={assignedDocumentsQuery.isLoading}
          isError={assignedDocumentsQuery.isError}
          onUploadDocuments={handleUploadDocuments}
        />
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
          {canAccessOrganizationSettings ? (
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={isActive(links.organizationSettings)}>
                <NavLink to={links.organizationSettings}>
                  <LayoutGrid />
                  <span>Organization Settings</span>
                </NavLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ) : null}
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function WorkspaceSwitcher({
  workspace,
  workspaces,
  workspaceLabel,
  onSelectWorkspace,
  onViewAllWorkspaces,
}: WorkspaceSwitcherProps) {
  const [open, setOpen] = useState(false);
  const workspaceInitials = getWorkspaceInitials(workspaceLabel);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <SidebarMenuButton
          type="button"
          size="lg"
          className="w-full justify-between border border-transparent bg-topbar/70 shadow-none hover:bg-accent hover:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:justify-center"
          tooltip={workspaceLabel}
        >
          <span className="flex min-w-0 items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-md bg-sidebar-accent text-xs font-semibold uppercase text-sidebar-foreground">
              {workspaceInitials}
            </span>
            <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
              <span className="block truncate text-sm font-semibold">{workspaceLabel}</span>
            </span>
          </span>
          <ChevronsUpDown className="size-4 opacity-60 group-data-[collapsible=icon]:hidden" />
        </SidebarMenuButton>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        className="min-w-64 w-(--radix-popover-trigger-width) p-0"
      >
        <Search>
          <SearchInput placeholder="Search workspaces..." />
          <SearchList>
            <SearchEmpty>No workspaces found.</SearchEmpty>
            <SearchGroup heading="Workspaces">
              {workspaces.map((item) => {
                const itemLabel = item.name || "Workspace";
                const itemInitials = getWorkspaceInitials(itemLabel);
                return (
                  <SearchItem
                    key={item.id}
                    value={item.slug ? `${itemLabel} ${item.slug}` : itemLabel}
                    onSelect={() => {
                      onSelectWorkspace(item.id);
                      setOpen(false);
                    }}
                  >
                    <span className="flex size-7 items-center justify-center rounded-md bg-sidebar-accent text-[11px] font-semibold uppercase text-sidebar-foreground">
                      {itemInitials}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{itemLabel}</span>
                    <Check
                      className={cn(
                        "ml-auto size-4 text-foreground",
                        item.id === workspace.id ? "opacity-100" : "opacity-0",
                      )}
                    />
                  </SearchItem>
                );
              })}
            </SearchGroup>
            <SearchSeparator />
            <SearchGroup heading="Actions">
              <SearchItem
                value="View all workspaces"
                onSelect={() => {
                  onViewAllWorkspaces();
                  setOpen(false);
                }}
              >
                <LayoutGrid />
                <span>View all workspaces</span>
              </SearchItem>
            </SearchGroup>
          </SearchList>
        </Search>
      </PopoverContent>
    </Popover>
  );
}

function WorkspaceNavSection({
  navItems,
  isActive,
  workspaceAvatarItems,
  workspacePresenceLabel,
}: WorkspaceNavSectionProps) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel asChild>
        <WorkspacePresenceSummary items={workspaceAvatarItems} label={workspacePresenceLabel} />
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {navItems.map((item) => {
            const Icon = item.Icon;
            return (
              <SidebarMenuItem key={item.key}>
                <SidebarMenuButton asChild isActive={isActive(item.to)}>
                  <NavLink to={item.to}>
                    <Icon />
                    <span>{item.label}</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

function WorkspacePresenceSummary({
  items,
  label,
  className,
  ...props
}: WorkspacePresenceSummaryProps) {
  return (
    <div className={cn("w-full items-center justify-between gap-2", className)} {...props}>
      <span>Workspace</span>
      <Tooltip>
        <TooltipTrigger asChild>
          <AvatarGroup size={18} max={3} className="shrink-0">
            {items.map((item) => (
              <Avatar key={item.id} aria-hidden="true" title={item.label}>
                <AvatarFallback className="bg-sidebar-accent text-[8px] font-semibold text-sidebar-foreground">
                  {item.initials}
                </AvatarFallback>
              </Avatar>
            ))}
          </AvatarGroup>
        </TooltipTrigger>
        <TooltipContent side="right" align="center" className="max-w-[220px] whitespace-pre-line">
          {label}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

function AssignedDocumentsSection({
  assignedDocuments,
  documentsPresenceById,
  activeDocId,
  isLoading,
  isError,
  onUploadDocuments,
}: AssignedDocumentsSectionProps) {
  return (
    <Collapsible defaultOpen className="group/collapsible group-data-[collapsible=icon]:hidden">
      <SidebarGroup>
        <SidebarGroupLabel asChild>
          <CollapsibleTrigger type="button" className="w-full justify-between gap-2 pr-8">
            <span>My Documents</span>
            <ChevronDown className="size-3 transition-transform group-data-[state=open]/collapsible:rotate-180" />
          </CollapsibleTrigger>
        </SidebarGroupLabel>
        <SidebarGroupAction title="Upload documents" onClick={onUploadDocuments}>
          <Plus />
          <span className="sr-only">Upload documents</span>
        </SidebarGroupAction>
        <CollapsibleContent>
          <SidebarGroupContent>
            {isLoading ? (
              <SidebarMenu>
                {Array.from({ length: ASSIGNED_DOCUMENT_SKELETON_COUNT }, (_, index) => (
                  <SidebarMenuItem key={`assigned-documents-skeleton-${index}`}>
                    <SidebarMenuSkeleton showIcon />
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            ) : isError ? (
              <p className="px-2 py-2 text-xs text-sidebar-foreground/70">
                Unable to load assigned documents.
              </p>
            ) : assignedDocuments.length === 0 ? (
              <p className="px-2 py-2 text-xs text-sidebar-foreground/70">
                No assigned documents yet.
              </p>
            ) : (
              <SidebarMenu>
                {assignedDocuments.map((document) => (
                  <AssignedDocumentItem
                    key={document.id}
                    document={document}
                    documentsPresenceById={documentsPresenceById}
                    isActive={document.id === activeDocId}
                  />
                ))}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </CollapsibleContent>
      </SidebarGroup>
    </Collapsible>
  );
}

function AssignedDocumentItem({
  document,
  documentsPresenceById,
  isActive,
}: AssignedDocumentItemProps) {
  const documentParticipants = documentsPresenceById.get(document.id) ?? [];
  const documentAvatars = buildAvatarItems(documentParticipants);
  const documentPresenceLabel = documentAvatars.map((item) => item.label).join(", ");

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={isActive}>
        <NavLink
          to={buildDocumentDetailUrl(
            document.workspaceId,
            document.id,
            { tab: "activity" },
          )}
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
                <TooltipContent side="right" align="center" className="max-w-[220px] whitespace-pre-line">
                  {documentPresenceLabel}
                </TooltipContent>
              </Tooltip>
            </div>
          ) : null}
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

function getWorkspaceInitials(value: string) {
  return value
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
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

function buildAvatarItems(participants: PresenceParticipant[]): AvatarItem[] {
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
