import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addGroupMember,
  addGroupOwner,
  createGroup,
  deleteGroup,
  listGroupMembers,
  listGroupOwners,
  listGroups,
  removeGroupMember,
  removeGroupOwner,
  updateGroup,
  type Group,
  type GroupCreateRequest,
  type GroupMembers,
  type GroupOwners,
  type GroupUpdateRequest,
} from "@/api/groups/api";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useAdminUsersQuery } from "@/hooks/admin";
import { AccessCommandBar, PrincipalIdentityCell, resolveAccessActionState } from "@/pages/SharedAccess/components";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { SettingsDrawer } from "@/pages/Workspace/sections/Settings/components/SettingsDrawer";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";
import { useOrganizationSettingsSection } from "../sectionContext";

const GROUPS_QUERY_KEY = ["organization", "groups"] as const;

function useGroupsQuery(enabled: boolean) {
  return useQuery({
    queryKey: GROUPS_QUERY_KEY,
    queryFn: ({ signal }) => listGroups({ signal }),
    enabled,
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function GroupsSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const { params } = useOrganizationSettingsSection();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const canManageGroups = hasPermission("groups.manage_all");
  const canReadGroups = hasPermission("groups.read_all") || canManageGroups;
  const canManageMembers = hasPermission("groups.members.manage_all") || canManageGroups;
  const canReadMembers = hasPermission("groups.members.read_all") || canManageMembers;
  const canReadUsers = hasPermission("users.read_all") || hasPermission("users.manage_all");

  const groupsQuery = useGroupsQuery(canReadGroups);
  const usersQuery = useAdminUsersQuery({ enabled: canReadUsers, pageSize: 200 });
  const createGroupMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GROUPS_QUERY_KEY }),
  });
  const updateGroupMutation = useMutation({
    mutationFn: ({ groupId, payload }: { groupId: string; payload: Parameters<typeof updateGroup>[1] }) =>
      updateGroup(groupId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GROUPS_QUERY_KEY }),
  });
  const deleteGroupMutation = useMutation({
    mutationFn: (groupId: string) => deleteGroup(groupId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GROUPS_QUERY_KEY }),
  });
  const addGroupMemberMutation = useMutation({
    mutationFn: ({ groupId, memberId }: { groupId: string; memberId: string }) =>
      addGroupMember(groupId, memberId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["organization", "groups", variables.groupId, "members"] });
    },
  });
  const removeGroupMemberMutation = useMutation({
    mutationFn: ({ groupId, memberId }: { groupId: string; memberId: string }) =>
      removeGroupMember(groupId, memberId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["organization", "groups", variables.groupId, "members"] });
    },
  });
  const addGroupOwnerMutation = useMutation({
    mutationFn: ({ groupId, ownerId }: { groupId: string; ownerId: string }) =>
      addGroupOwner(groupId, ownerId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["organization", "groups", variables.groupId, "owners"] });
    },
  });
  const removeGroupOwnerMutation = useMutation({
    mutationFn: ({ groupId, ownerId }: { groupId: string; ownerId: string }) =>
      removeGroupOwner(groupId, ownerId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["organization", "groups", variables.groupId, "owners"] });
    },
  });

  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);
  const [searchValue, setSearchValue] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | Group["source"]>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const selectedParam = params[0];
  const isCreateOpen = selectedParam === "new";
  const selectedGroupId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const groups = groupsQuery.data?.items ?? [];
  const selectedGroup = groups.find((group) => group.id === selectedGroupId);
  const filteredGroups = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    return groups.filter((group) => {
      if (sourceFilter !== "all" && group.source !== sourceFilter) {
        return false;
      }
      if (statusFilter === "active" && !group.is_active) {
        return false;
      }
      if (statusFilter === "inactive" && group.is_active) {
        return false;
      }
      if (!query) {
        return true;
      }
      const haystack = `${group.display_name} ${group.slug} ${group.description ?? ""}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [groups, searchValue, sourceFilter, statusFilter]);

  const basePath = "/organization/access/groups";
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openCreateDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openGroupDrawer = (groupId: string) => navigate(`${basePath}/${encodeURIComponent(groupId)}${suffix}`);

  if (!canReadGroups) {
    return <Alert tone="danger">You do not have permission to access groups.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {groupsQuery.isError ? (
        <Alert tone="danger">
          {groupsQuery.error instanceof Error ? groupsQuery.error.message : "Unable to load groups."}
        </Alert>
      ) : null}
      {usersQuery.isError ? (
        <Alert tone="warning">
          {usersQuery.error instanceof Error
            ? usersQuery.error.message
            : "Unable to load users for membership actions."}
        </Alert>
      ) : null}
      <SettingsSection
        title="Groups"
        description={
          groupsQuery.isLoading
            ? "Loading groups..."
            : `${filteredGroups.length} group${filteredGroups.length === 1 ? "" : "s"}`
        }
        actions={
          canManageGroups ? (
            <Button type="button" size="sm" onClick={openCreateDrawer}>
              Create group
            </Button>
          ) : null
        }
      >
        <AccessCommandBar
          searchValue={searchValue}
          onSearchValueChange={setSearchValue}
          searchPlaceholder="Search groups"
          searchAriaLabel="Search groups"
          controls={
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={sourceFilter}
                onValueChange={(value) => setSourceFilter(value as "all" | Group["source"])}
              >
                <SelectTrigger className="w-full min-w-36 sm:w-40">
                  <SelectValue placeholder="Filter source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sources</SelectItem>
                  <SelectItem value="internal">Internal</SelectItem>
                  <SelectItem value="idp">Provider-managed</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={statusFilter}
                onValueChange={(value) => setStatusFilter(value as "all" | "active" | "inactive")}
              >
                <SelectTrigger className="w-full min-w-36 sm:w-36">
                  <SelectValue placeholder="Filter status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          }
        />

        {groupsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading groups...</p>
        ) : filteredGroups.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No groups match your current filters.
          </p>
        ) : (
          <ResponsiveAdminTable
            items={filteredGroups}
            getItemKey={(group) => group.id}
            mobileListLabel="Organization groups"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Group</TableHead>
                      <TableHead className="px-4">Membership</TableHead>
                      <TableHead className="px-4">Source</TableHead>
                      <TableHead className="px-4">Status</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredGroups.map((group) => (
                      <TableRow key={group.id}>
                        <TableCell className="px-4 py-3">
                          <PrincipalIdentityCell
                            principalType="group"
                            title={group.display_name}
                            subtitle={group.slug}
                            detail={group.description ?? undefined}
                          />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant="outline">{group.membership_mode}</Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant={group.source === "idp" ? "outline" : "secondary"}>
                            {group.source === "idp" ? "Provider-managed" : "Internal"}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant={group.is_active ? "secondary" : "outline"}>
                            {group.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3 text-right">
                          <Button type="button" variant="ghost" size="sm" onClick={() => openGroupDrawer(group.id)}>
                            {canManageGroups ? "Manage" : "View"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(group) => (
              <>
                <PrincipalIdentityCell
                  principalType="group"
                  title={group.display_name}
                  subtitle={group.slug}
                  detail={group.description ?? undefined}
                />
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Membership</dt>
                  <dd>
                    <Badge variant="outline">{group.membership_mode}</Badge>
                  </dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Source</dt>
                  <dd>
                    <Badge variant={group.source === "idp" ? "outline" : "secondary"}>
                      {group.source === "idp" ? "Provider-managed" : "Internal"}
                    </Badge>
                  </dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                  <dd>
                    <Badge variant={group.is_active ? "secondary" : "outline"}>
                      {group.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </dd>
                </dl>
                <div className="flex justify-end">
                  <Button type="button" variant="ghost" size="sm" onClick={() => openGroupDrawer(group.id)}>
                    {canManageGroups ? "Manage" : "View"}
                  </Button>
                </div>
              </>
            )}
          />
        )}
      </SettingsSection>

      <GroupDrawer
        open={isCreateOpen && canManageGroups}
        mode="create"
        canReadMembers={canReadMembers}
        canReadUsers={canReadUsers}
        canManageMembers={canManageMembers}
        availableUsers={usersQuery.users}
        onClose={closeDrawer}
        onCreate={async (payload) => {
          setFeedbackMessage(null);
          await createGroupMutation.mutateAsync(payload);
          setFeedbackMessage({ tone: "success", message: "Group created." });
          closeDrawer();
        }}
        isSaving={createGroupMutation.isPending}
      />

      <GroupDrawer
        open={Boolean(selectedGroupId)}
        mode="edit"
        group={selectedGroup}
        canReadMembers={canReadMembers}
        canReadUsers={canReadUsers}
        canManageMembers={canManageMembers}
        availableUsers={usersQuery.users}
        canManage={canManageGroups}
        onClose={closeDrawer}
        onUpdate={async (payload) => {
          if (!selectedGroupId) return;
          setFeedbackMessage(null);
          await updateGroupMutation.mutateAsync({ groupId: selectedGroupId, payload });
          setFeedbackMessage({ tone: "success", message: "Group updated." });
          closeDrawer();
        }}
        onDelete={async () => {
          if (!selectedGroupId) return;
          setFeedbackMessage(null);
          await deleteGroupMutation.mutateAsync(selectedGroupId);
          setFeedbackMessage({ tone: "success", message: "Group deleted." });
          closeDrawer();
        }}
        onAddMember={async (memberId) => {
          if (!selectedGroupId) return;
          await addGroupMemberMutation.mutateAsync({ groupId: selectedGroupId, memberId });
        }}
        onRemoveMember={async (memberId) => {
          if (!selectedGroupId) return;
          await removeGroupMemberMutation.mutateAsync({ groupId: selectedGroupId, memberId });
        }}
        onAddOwner={async (ownerId) => {
          if (!selectedGroupId) return;
          await addGroupOwnerMutation.mutateAsync({ groupId: selectedGroupId, ownerId });
        }}
        onRemoveOwner={async (ownerId) => {
          if (!selectedGroupId) return;
          await removeGroupOwnerMutation.mutateAsync({ groupId: selectedGroupId, ownerId });
        }}
        isSaving={updateGroupMutation.isPending}
        isMutatingRelations={
          addGroupMemberMutation.isPending ||
          removeGroupMemberMutation.isPending ||
          addGroupOwnerMutation.isPending ||
          removeGroupOwnerMutation.isPending
        }
        isDeleting={deleteGroupMutation.isPending}
      />
    </div>
  );
}

function GroupDrawer({
  open,
  mode,
  group,
  canManage = true,
  canReadMembers,
  canReadUsers,
  canManageMembers,
  availableUsers,
  onClose,
  onCreate,
  onUpdate,
  onDelete,
  onAddMember,
  onRemoveMember,
  onAddOwner,
  onRemoveOwner,
  isSaving,
  isMutatingRelations = false,
  isDeleting = false,
}: {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly group?: Group;
  readonly canManage?: boolean;
  readonly canReadMembers: boolean;
  readonly canReadUsers: boolean;
  readonly canManageMembers: boolean;
  readonly availableUsers: readonly { id: string; email: string; display_name?: string | null }[];
  readonly onClose: () => void;
  readonly onCreate?: (payload: GroupCreateRequest) => Promise<void>;
  readonly onUpdate?: (payload: GroupUpdateRequest) => Promise<void>;
  readonly onDelete?: () => Promise<void>;
  readonly onAddMember?: (memberId: string) => Promise<void>;
  readonly onRemoveMember?: (memberId: string) => Promise<void>;
  readonly onAddOwner?: (ownerId: string) => Promise<void>;
  readonly onRemoveOwner?: (ownerId: string) => Promise<void>;
  readonly isSaving: boolean;
  readonly isMutatingRelations?: boolean;
  readonly isDeleting?: boolean;
}) {
  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [activeTab, setActiveTab] = useState<"details" | "members" | "owners">("details");
  const [memberSearch, setMemberSearch] = useState("");
  const [ownerSearch, setOwnerSearch] = useState("");
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [selectedOwnerId, setSelectedOwnerId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const membersQuery = useQuery<GroupMembers>({
    queryKey: ["organization", "groups", group?.id, "members"],
    queryFn: () => listGroupMembers(group!.id),
    enabled: open && mode === "edit" && canReadMembers && Boolean(group?.id),
    staleTime: 10_000,
  });
  const ownersQuery = useQuery<GroupOwners>({
    queryKey: ["organization", "groups", group?.id, "owners"],
    queryFn: () => listGroupOwners(group!.id),
    enabled: open && mode === "edit" && canReadMembers && Boolean(group?.id),
    staleTime: 10_000,
  });

  useEffect(() => {
    if (!open) {
      setError(null);
      return;
    }
    setActiveTab("details");
    setMemberSearch("");
    setOwnerSearch("");
    setSelectedMemberId("");
    setSelectedOwnerId("");
    if (mode === "edit" && group) {
      setDisplayName(group.display_name);
      setSlug(group.slug);
      setDescription(group.description ?? "");
    } else {
      setDisplayName("");
      setSlug("");
      setDescription("");
    }
  }, [group, mode, open]);

  const memberIds = useMemo(
    () => new Set((membersQuery.data?.items ?? []).map((member) => member.user_id)),
    [membersQuery.data?.items],
  );
  const ownerIds = useMemo(
    () => new Set((ownersQuery.data?.items ?? []).map((owner) => owner.user_id)),
    [ownersQuery.data?.items],
  );
  const memberCandidates = useMemo(() => {
    const query = memberSearch.trim().toLowerCase();
    return availableUsers
      .filter((user) => !memberIds.has(user.id))
      .filter((user) => {
        if (!query) {
          return true;
        }
        return `${user.display_name ?? ""} ${user.email}`.toLowerCase().includes(query);
      })
      .slice(0, 100);
  }, [availableUsers, memberIds, memberSearch]);
  const ownerCandidates = useMemo(() => {
    const query = ownerSearch.trim().toLowerCase();
    return availableUsers
      .filter((user) => !ownerIds.has(user.id))
      .filter((user) => {
        if (!query) {
          return true;
        }
        return `${user.display_name ?? ""} ${user.email}`.toLowerCase().includes(query);
      })
      .slice(0, 100);
  }, [availableUsers, ownerIds, ownerSearch]);
  const membershipReadOnlyReason =
    group?.source === "idp"
      ? "This provider-managed group is read-only in ADE."
      : group?.membership_mode === "dynamic"
        ? "Dynamic memberships are managed by your identity provider."
        : null;
  const addMemberState = resolveAccessActionState({
    isDisabled:
      !canManageMembers ||
      !canReadUsers ||
      !selectedMemberId ||
      Boolean(membershipReadOnlyReason) ||
      isMutatingRelations,
    reasonCode: !canManageMembers || !canReadUsers
      ? "perm_missing"
      : group?.source === "idp"
        ? "provider_managed"
        : group?.membership_mode === "dynamic"
          ? "dynamic_membership"
          : !selectedMemberId
            ? "invalid_selection"
            : null,
    reasonText: !canReadUsers
      ? "You need users.read_all to browse and select users."
      : !canManageMembers
        ? "You need group member manage permission to edit members."
        : undefined,
  });
  const addOwnerState = resolveAccessActionState({
    isDisabled:
      !canManage ||
      !canReadUsers ||
      !selectedOwnerId ||
      Boolean(membershipReadOnlyReason) ||
      isMutatingRelations,
    reasonCode: !canManage || !canReadUsers
      ? "perm_missing"
      : group?.source === "idp"
        ? "provider_managed"
        : group?.membership_mode === "dynamic"
          ? "dynamic_membership"
          : !selectedOwnerId
            ? "invalid_selection"
            : null,
    reasonText: !canManage
      ? "You need groups.manage_all permission to edit owners."
      : !canReadUsers
        ? "You need users.read_all to browse and select users."
        : undefined,
  });

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!displayName.trim()) {
      setError("Group display name is required.");
      return;
    }
    try {
      if (mode === "create") {
        if (!onCreate) {
          throw new Error("Create handler is not configured.");
        }
        await onCreate({
          display_name: displayName.trim(),
          slug: slug.trim() || undefined,
          description: description.trim() || null,
          membership_mode: "assigned",
          source: "internal",
        });
      } else {
        if (!onUpdate) {
          throw new Error("Update handler is not configured.");
        }
        await onUpdate({
          display_name: displayName.trim(),
          description: description.trim() || null,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save group.");
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title={mode === "create" ? "Create group" : group?.display_name ?? "Group"}
      description={
        mode === "create"
          ? "Create a group for principal-based role assignment."
          : "Update group details and review current membership."
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        {mode === "create" ? (
          <>
            <FormField label="Display name" required>
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Analytics Team"
                disabled={!canManage || isSaving}
              />
            </FormField>
            <FormField label="Slug">
              <Input
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="analytics-team"
                disabled={!canManage || isSaving}
              />
            </FormField>
            <FormField label="Description">
              <Input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Optional"
                disabled={!canManage || isSaving}
              />
            </FormField>
          </>
        ) : (
          <TabsRoot value={activeTab} onValueChange={(value) => setActiveTab(value as "details" | "members" | "owners")}>
            <TabsList className="mb-3 flex flex-wrap gap-2">
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="members">Members</TabsTrigger>
              <TabsTrigger value="owners">Owners</TabsTrigger>
            </TabsList>

            <TabsContent value="details" className="space-y-4">
              <FormField label="Display name" required>
                <Input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Analytics Team"
                  disabled={!canManage || isSaving}
                />
              </FormField>
              <FormField label="Description">
                <Input
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Optional"
                  disabled={!canManage || isSaving}
                />
              </FormField>
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">Slug: {group?.slug ?? "—"}</Badge>
                <Badge variant={group?.source === "idp" ? "outline" : "secondary"}>
                  {group?.source === "idp" ? "Provider-managed" : "Internal"}
                </Badge>
                <Badge variant={group?.membership_mode === "dynamic" ? "outline" : "secondary"}>
                  {group?.membership_mode === "dynamic" ? "Dynamic" : "Assigned"}
                </Badge>
              </div>
            </TabsContent>

            <TabsContent value="members" className="space-y-3">
              {!canReadMembers ? (
                <p className="text-sm text-muted-foreground">
                  You need group-membership read permission to view members.
                </p>
              ) : (
                <>
                  {membershipReadOnlyReason ? (
                    <Alert tone="info">{membershipReadOnlyReason}</Alert>
                  ) : null}
                  <div className="rounded-lg border border-border p-3">
                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
                      <FormField label="Search users">
                        <Input
                          value={memberSearch}
                          onChange={(event) => setMemberSearch(event.target.value)}
                          placeholder="Search users"
                          disabled={!canReadUsers || isMutatingRelations}
                        />
                      </FormField>
                      <FormField label="User">
                        <Select
                          value={selectedMemberId}
                          onValueChange={setSelectedMemberId}
                          disabled={!canReadUsers || isMutatingRelations}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a user" />
                          </SelectTrigger>
                          <SelectContent>
                            {memberCandidates.length === 0 ? (
                              <SelectItem value="__none__" disabled>
                                No eligible users
                              </SelectItem>
                            ) : (
                              memberCandidates.map((user) => (
                                <SelectItem key={user.id} value={user.id}>
                                  {user.display_name?.trim() || user.email}
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      </FormField>
                      <Button
                        type="button"
                        disabled={addMemberState.disabled}
                        onClick={async () => {
                          if (!selectedMemberId || !onAddMember) {
                            return;
                          }
                          setError(null);
                          try {
                            await onAddMember(selectedMemberId);
                            setSelectedMemberId("");
                            await membersQuery.refetch();
                          } catch (relationError) {
                            setError(
                              relationError instanceof Error
                                ? relationError.message
                                : "Unable to add member.",
                            );
                          }
                        }}
                      >
                        Add member
                      </Button>
                    </div>
                    {addMemberState.reasonText ? (
                      <p className="mt-2 text-xs text-muted-foreground">{addMemberState.reasonText}</p>
                    ) : null}
                  </div>
                  {membersQuery.isLoading ? (
                    <p className="text-sm text-muted-foreground">Loading members...</p>
                  ) : (membersQuery.data?.items.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No direct members.</p>
                  ) : (
                    <div className="space-y-2">
                      {(membersQuery.data?.items ?? []).map((member) => {
                        const removeMemberState = resolveAccessActionState({
                          isDisabled:
                            !canManageMembers ||
                            Boolean(membershipReadOnlyReason) ||
                            isMutatingRelations,
                          reasonCode: !canManageMembers
                            ? "perm_missing"
                            : group?.source === "idp"
                              ? "provider_managed"
                              : group?.membership_mode === "dynamic"
                                ? "dynamic_membership"
                                : null,
                          reasonText: !canManageMembers
                            ? "You need group member manage permission to remove members."
                            : undefined,
                        });
                        return (
                          <div
                            key={member.user_id}
                            className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
                          >
                            <div>
                              <p className="text-sm font-semibold text-foreground">
                                {member.display_name?.trim() || member.email}
                              </p>
                              <p className="text-xs text-muted-foreground">{member.email}</p>
                            </div>
                            <DrawerActionButton
                              label="Remove"
                              tone="danger"
                              disabled={removeMemberState.disabled}
                              reason={removeMemberState.reasonText}
                              onClick={async () => {
                                if (!onRemoveMember) {
                                  return;
                                }
                                setError(null);
                                try {
                                  await onRemoveMember(member.user_id);
                                  await membersQuery.refetch();
                                } catch (relationError) {
                                  setError(
                                    relationError instanceof Error
                                      ? relationError.message
                                      : "Unable to remove member.",
                                  );
                                }
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </TabsContent>

            <TabsContent value="owners" className="space-y-3">
              {!canReadMembers ? (
                <p className="text-sm text-muted-foreground">
                  You need group-membership read permission to view owners.
                </p>
              ) : (
                <>
                  {membershipReadOnlyReason ? (
                    <Alert tone="info">{membershipReadOnlyReason}</Alert>
                  ) : null}
                  <div className="rounded-lg border border-border p-3">
                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
                      <FormField label="Search users">
                        <Input
                          value={ownerSearch}
                          onChange={(event) => setOwnerSearch(event.target.value)}
                          placeholder="Search users"
                          disabled={!canReadUsers || isMutatingRelations}
                        />
                      </FormField>
                      <FormField label="User">
                        <Select
                          value={selectedOwnerId}
                          onValueChange={setSelectedOwnerId}
                          disabled={!canReadUsers || isMutatingRelations}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a user" />
                          </SelectTrigger>
                          <SelectContent>
                            {ownerCandidates.length === 0 ? (
                              <SelectItem value="__none__" disabled>
                                No eligible users
                              </SelectItem>
                            ) : (
                              ownerCandidates.map((user) => (
                                <SelectItem key={user.id} value={user.id}>
                                  {user.display_name?.trim() || user.email}
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      </FormField>
                      <Button
                        type="button"
                        disabled={addOwnerState.disabled}
                        onClick={async () => {
                          if (!selectedOwnerId || !onAddOwner) {
                            return;
                          }
                          setError(null);
                          try {
                            await onAddOwner(selectedOwnerId);
                            setSelectedOwnerId("");
                            await ownersQuery.refetch();
                          } catch (relationError) {
                            setError(
                              relationError instanceof Error
                                ? relationError.message
                                : "Unable to add owner.",
                            );
                          }
                        }}
                      >
                        Add owner
                      </Button>
                    </div>
                    {addOwnerState.reasonText ? (
                      <p className="mt-2 text-xs text-muted-foreground">{addOwnerState.reasonText}</p>
                    ) : null}
                  </div>
                  {ownersQuery.isLoading ? (
                    <p className="text-sm text-muted-foreground">Loading owners...</p>
                  ) : (ownersQuery.data?.items.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No owners assigned.</p>
                  ) : (
                    <div className="space-y-2">
                      {(ownersQuery.data?.items ?? []).map((owner) => {
                        const removeOwnerState = resolveAccessActionState({
                          isDisabled:
                            !canManage ||
                            Boolean(membershipReadOnlyReason) ||
                            isMutatingRelations,
                          reasonCode: !canManage
                            ? "perm_missing"
                            : group?.source === "idp"
                              ? "provider_managed"
                              : group?.membership_mode === "dynamic"
                                ? "dynamic_membership"
                                : null,
                          reasonText: !canManage
                            ? "You need groups.manage_all permission to remove owners."
                            : undefined,
                        });
                        return (
                          <div
                            key={owner.user_id}
                            className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
                          >
                            <div>
                              <p className="text-sm font-semibold text-foreground">
                                {owner.display_name?.trim() || owner.email}
                              </p>
                              <p className="text-xs text-muted-foreground">{owner.email}</p>
                            </div>
                            <DrawerActionButton
                              label="Remove"
                              tone="danger"
                              disabled={removeOwnerState.disabled}
                              reason={removeOwnerState.reasonText}
                              onClick={async () => {
                                if (!onRemoveOwner) {
                                  return;
                                }
                                setError(null);
                                try {
                                  await onRemoveOwner(owner.user_id);
                                  await ownersQuery.refetch();
                                } catch (relationError) {
                                  setError(
                                    relationError instanceof Error
                                      ? relationError.message
                                      : "Unable to remove owner.",
                                  );
                                }
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </TabsContent>
          </TabsRoot>
        )}
        <div className="flex items-center justify-between pt-2">
          {mode === "edit" && onDelete && canManage ? (
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                void onDelete().catch((err) =>
                  setError(err instanceof Error ? err.message : "Unable to delete group."),
                );
              }}
              disabled={isDeleting}
            >
              Delete
            </Button>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Close
            </Button>
            {canManage ? (
              <Button type="submit" disabled={isSaving}>
                {mode === "create" ? "Create group" : "Save group"}
              </Button>
            ) : null}
          </div>
        </div>
      </form>
    </SettingsDrawer>
  );
}

function DrawerActionButton({
  label,
  disabled,
  reason,
  onClick,
  tone = "default",
}: {
  readonly label: string;
  readonly disabled: boolean;
  readonly reason: string | null;
  readonly onClick: () => void | Promise<void>;
  readonly tone?: "default" | "danger";
}) {
  const button = (
    <Button
      type="button"
      variant={tone === "danger" ? "destructive" : "ghost"}
      size="sm"
      disabled={disabled}
      onClick={() => {
        void onClick();
      }}
    >
      {label}
    </Button>
  );

  if (!disabled || !reason) {
    return button;
  }

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="top">{reason}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
