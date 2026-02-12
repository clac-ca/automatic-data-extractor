import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { LoadingState } from "@/components/layout";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";

import {
  normalizeSettingsError,
  useAddOrganizationGroupMemberMutation,
  useAddOrganizationGroupOwnerMutation,
  useCreateOrganizationGroupMutation,
  useDeleteOrganizationGroupMutation,
  useOrganizationGroupDetailQuery,
  useOrganizationGroupMembersQuery,
  useOrganizationGroupOwnersQuery,
  useOrganizationGroupsListQuery,
  useOrganizationUsersListQuery,
  useRemoveOrganizationGroupMemberMutation,
  useRemoveOrganizationGroupOwnerMutation,
  useUpdateOrganizationGroupMutation,
} from "../../data";
import { settingsPaths } from "../../routing/contracts";
import {
  SettingsAccessDenied,
  SettingsCommandBar,
  SettingsDataTable,
  SettingsDetailLayout,
  SettingsDetailSection,
  SettingsEmptyState,
  SettingsErrorState,
  SettingsFeedbackRegion,
  SettingsFormErrorSummary,
  SettingsListLayout,
  SettingsStickyActionBar,
  useSettingsErrorSummary,
  useSettingsListState,
} from "../../shared";

function canViewGroups(permissions: ReadonlySet<string>) {
  return permissions.has("groups.read_all") || permissions.has("groups.manage_all");
}

function canManageGroups(permissions: ReadonlySet<string>) {
  return permissions.has("groups.manage_all");
}

const GROUP_CREATE_SECTIONS = [{ id: "group-profile", label: "Group profile" }] as const;

const GROUP_DETAIL_SECTIONS = [
  { id: "profile", label: "Profile" },
  { id: "members", label: "Members" },
  { id: "owners", label: "Owners" },
  { id: "lifecycle", label: "Lifecycle", tone: "danger" as const },
] as const;

export function OrganizationGroupsListPage() {
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const listState = useSettingsListState({
    defaults: { sort: "display_name", order: "asc", pageSize: 25 },
  });
  const query = useOrganizationGroupsListQuery(listState.state.q);

  if (!canViewGroups(permissions)) {
    return <SettingsAccessDenied returnHref={settingsPaths.home} />;
  }

  return (
    <SettingsListLayout
      title="Groups"
      subtitle="Create and manage organization groups with explicit owner and member controls."
      breadcrumbs={[{ label: "Settings", href: settingsPaths.home }, { label: "Organization" }, { label: "Groups" }]}
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search groups by name or slug"
          primaryAction={
            canManageGroups(permissions) ? (
              <Button asChild>
                <Link to={listState.withCurrentSearch(settingsPaths.organization.groupsCreate)}>Create group</Link>
              </Button>
            ) : null
          }
        />
      }
    >
      {query.isLoading ? <LoadingState title="Loading groups" className="min-h-[200px]" /> : null}
      {query.isError ? (
        <SettingsErrorState
          title="Unable to load groups"
          message={normalizeSettingsError(query.error, "Unable to load groups.").message}
        />
      ) : null}
      {query.isSuccess && query.data.items.length === 0 ? (
        <SettingsEmptyState
          title="No groups found"
          description="Create a group to simplify membership and role assignment workflows."
          action={
            canManageGroups(permissions) ? (
              <Button asChild size="sm">
                <Link to={settingsPaths.organization.groupsCreate}>Create group</Link>
              </Button>
            ) : null
          }
        />
      ) : null}
      {query.isSuccess && query.data.items.length > 0 ? (
        <SettingsDataTable
          rows={query.data.items}
          columns={[
            {
              id: "group",
              header: "Group",
              cell: (group) => (
                <>
                  <p className="font-medium text-foreground">{group.display_name}</p>
                  <p className="text-xs text-muted-foreground">{group.slug}</p>
                </>
              ),
            },
            {
              id: "source",
              header: "Source",
              cell: (group) => (
                <Badge variant={group.source === "idp" ? "outline" : "secondary"}>{group.source}</Badge>
              ),
            },
            {
              id: "mode",
              header: "Mode",
              cell: (group) => <p className="text-sm text-muted-foreground">{group.membership_mode}</p>,
            },
          ]}
          getRowId={(group) => group.id}
          onRowOpen={(group) =>
            navigate(listState.withCurrentSearch(settingsPaths.organization.groupDetail(group.id)))
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={query.data.items.length}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey="settings-organization-groups-list-row"
        />
      ) : null}
    </SettingsListLayout>
  );
}

export function OrganizationGroupCreatePage() {
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const canManage = canManageGroups(permissions);
  const listState = useSettingsListState();

  const createGroupMutation = useCreateOrganizationGroupMutation();
  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [membershipMode, setMembershipMode] = useState<"assigned" | "dynamic">("assigned");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const errorSummary = useSettingsErrorSummary({
    fieldIdByKey: {
      display_name: "create-group-display-name",
      slug: "create-group-slug",
      description: "create-group-description",
    },
    fieldLabelByKey: {
      display_name: "Display name",
      slug: "Slug",
      description: "Description",
    },
  });

  useUnsavedChangesGuard({
    isDirty:
      displayName.trim().length > 0 ||
      slug.trim().length > 0 ||
      description.trim().length > 0 ||
      membershipMode !== "assigned",
    message: "You have unsaved changes for the new group.",
    shouldBypassNavigation: () => createGroupMutation.isPending,
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.organization.groups} />;
  }

  return (
    <SettingsDetailLayout
      title="Create group"
      subtitle="Define group identity and membership mode for organization-level access control."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Groups", href: listState.withCurrentSearch(settingsPaths.organization.groups) },
        { label: "Create" },
      ]}
      actions={
        <Button variant="outline" onClick={() => navigate(listState.withCurrentSearch(settingsPaths.organization.groups))}>
          Cancel
        </Button>
      }
      sections={GROUP_CREATE_SECTIONS}
      defaultSectionId="group-profile"
    >
      <SettingsFormErrorSummary summary={errorSummary.summary} />
      <SettingsFeedbackRegion
        messages={errorMessage ? [{ tone: "danger", message: errorMessage }] : []}
      />

      <SettingsDetailSection id="group-profile" title="Group profile">
        <FormField label="Display name" required error={errorSummary.getFieldError("display_name")}>
          <Input
            id="create-group-display-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Operations admins"
          />
        </FormField>
        <FormField label="Slug" hint="Optional URL-friendly identifier." error={errorSummary.getFieldError("slug")}>
          <Input
            id="create-group-slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="operations-admins"
          />
        </FormField>
        <FormField label="Description" error={errorSummary.getFieldError("description")}>
          <Input
            id="create-group-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Team with elevated controls"
          />
        </FormField>
        <FormField label="Membership mode">
          <Select value={membershipMode} onValueChange={(value) => setMembershipMode(value as "assigned" | "dynamic")}> 
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="assigned">Assigned</SelectItem>
              <SelectItem value="dynamic">Dynamic</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
      </SettingsDetailSection>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate(listState.withCurrentSearch(settingsPaths.organization.groups))}>
          Cancel
        </Button>
        <Button
          disabled={createGroupMutation.isPending}
          onClick={async () => {
            setErrorMessage(null);
            errorSummary.clearErrors();
            if (!displayName.trim()) {
              errorSummary.setClientErrors({ display_name: "Display name is required." });
              setErrorMessage("Please review the highlighted fields.");
              return;
            }
            try {
              const created = await createGroupMutation.mutateAsync({
                display_name: displayName.trim(),
                slug: slug.trim() || null,
                description: description.trim() || null,
                membership_mode: membershipMode,
                source: "internal",
                external_id: null,
              });
              navigate(listState.withCurrentSearch(settingsPaths.organization.groupDetail(created.id)), { replace: true });
            } catch (error) {
              const normalized = normalizeSettingsError(error, "Unable to create group.");
              setErrorMessage(normalized.message);
              errorSummary.setProblemErrors(normalized.fieldErrors);
            }
          }}
        >
          {createGroupMutation.isPending ? "Creating..." : "Create group"}
        </Button>
      </div>
    </SettingsDetailLayout>
  );
}

export function OrganizationGroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const { permissions } = useGlobalPermissions();
  const listState = useSettingsListState();

  const canView = canViewGroups(permissions);
  const canManage = canManageGroups(permissions);
  const canViewUsers = permissions.has("users.read_all") || permissions.has("users.manage_all");

  const groupQuery = useOrganizationGroupDetailQuery(groupId ?? null);
  const membersQuery = useOrganizationGroupMembersQuery(groupId ?? null);
  const ownersQuery = useOrganizationGroupOwnersQuery(groupId ?? null);
  const usersQuery = useOrganizationUsersListQuery("");

  const updateMutation = useUpdateOrganizationGroupMutation();
  const deleteMutation = useDeleteOrganizationGroupMutation();
  const addMemberMutation = useAddOrganizationGroupMemberMutation();
  const removeMemberMutation = useRemoveOrganizationGroupMemberMutation();
  const addOwnerMutation = useAddOrganizationGroupOwnerMutation();
  const removeOwnerMutation = useRemoveOrganizationGroupOwnerMutation();

  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [membershipMode, setMembershipMode] = useState<"assigned" | "dynamic">("assigned");
  const [isActive, setIsActive] = useState(true);
  const [memberToAdd, setMemberToAdd] = useState("");
  const [ownerToAdd, setOwnerToAdd] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (!groupQuery.data) {
      return;
    }
    setDisplayName(groupQuery.data.display_name);
    setDescription(groupQuery.data.description || "");
    setMembershipMode(groupQuery.data.membership_mode);
    setIsActive(groupQuery.data.is_active);
  }, [groupQuery.data]);

  const hasUnsavedChanges = useMemo(() => {
    if (!groupQuery.data) return false;
    return (
      groupQuery.data.display_name !== displayName ||
      (groupQuery.data.description || "") !== description ||
      groupQuery.data.membership_mode !== membershipMode ||
      groupQuery.data.is_active !== isActive
    );
  }, [description, displayName, groupQuery.data, isActive, membershipMode]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved group changes.",
    shouldBypassNavigation: () => updateMutation.isPending,
  });

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.organization.groups} />;
  }

  if (groupQuery.isLoading) {
    return <LoadingState title="Loading group" className="min-h-[300px]" />;
  }

  if (groupQuery.isError || !groupQuery.data) {
    return (
      <SettingsErrorState
        title="Group unavailable"
        message={normalizeSettingsError(groupQuery.error, "Unable to load group details.").message}
      />
    );
  }

  const group = groupQuery.data;
  const memberItems = membersQuery.data?.items ?? [];
  const ownerItems = ownersQuery.data?.items ?? [];

  const availableUsers = usersQuery.data?.items ?? [];
  const availableMembers = availableUsers.filter((user) => !memberItems.some((member) => member.user_id === user.id));
  const availableOwners = availableUsers.filter((user) => !ownerItems.some((owner) => owner.user_id === user.id));

  const saveChanges = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateMutation.mutateAsync({
        groupId: group.id,
        payload: {
          display_name: displayName.trim() || null,
          description: description.trim() || null,
          membership_mode: membershipMode,
          is_active: isActive,
        },
      });
      setSuccessMessage("Group settings saved.");
    } catch (error) {
      setErrorMessage(normalizeSettingsError(error, "Unable to save group settings.").message);
    }
  };

  return (
    <SettingsDetailLayout
      title={group.display_name}
      subtitle="Manage group profile, members, and owners."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Groups", href: listState.withCurrentSearch(settingsPaths.organization.groups) },
        { label: group.slug },
      ]}
      actions={<Badge variant={group.source === "idp" ? "outline" : "secondary"}>{group.source}</Badge>}
      sections={GROUP_DETAIL_SECTIONS}
      defaultSectionId="profile"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      <SettingsDetailSection id="profile" title="Profile">
        <FormField label="Display name" required>
          <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} disabled={!canManage || updateMutation.isPending} />
        </FormField>
        <FormField label="Slug">
          <Input value={group.slug} disabled />
        </FormField>
        <FormField label="Description">
          <Input value={description} onChange={(event) => setDescription(event.target.value)} disabled={!canManage || updateMutation.isPending} />
        </FormField>
        <FormField label="Membership mode">
          <Select value={membershipMode} onValueChange={(value) => setMembershipMode(value as "assigned" | "dynamic")}>
            <SelectTrigger disabled={!canManage || updateMutation.isPending}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="assigned">Assigned</SelectItem>
              <SelectItem value="dynamic">Dynamic</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} disabled={!canManage || updateMutation.isPending} />
          Group is active
        </label>
      </SettingsDetailSection>

      <SettingsDetailSection id="members" title="Members">
        {memberItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">No members assigned.</p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border/70">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {memberItems.map((member) => (
                  <TableRow key={member.user_id}>
                    <TableCell>
                      <p className="font-medium text-foreground">{member.display_name || member.email}</p>
                      <p className="text-xs text-muted-foreground">{member.email}</p>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={!canManage || removeMemberMutation.isPending}
                        onClick={async () => {
                          setErrorMessage(null);
                          setSuccessMessage(null);
                          try {
                            await removeMemberMutation.mutateAsync({ groupId: group.id, userId: member.user_id });
                            setSuccessMessage("Member removed.");
                          } catch (error) {
                            setErrorMessage(normalizeSettingsError(error, "Unable to remove member.").message);
                          }
                        }}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {canManage && canViewUsers ? (
          <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
            <FormField label="Add member">
              <Select value={memberToAdd} onValueChange={setMemberToAdd}>
                <SelectTrigger>
                  <SelectValue placeholder="Select user" />
                </SelectTrigger>
                <SelectContent>
                  {availableMembers.map((user) => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.display_name || user.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <Button
              disabled={!memberToAdd || addMemberMutation.isPending}
              onClick={async () => {
                setErrorMessage(null);
                setSuccessMessage(null);
                try {
                  await addMemberMutation.mutateAsync({ groupId: group.id, userId: memberToAdd });
                  setMemberToAdd("");
                  setSuccessMessage("Member added.");
                } catch (error) {
                  setErrorMessage(normalizeSettingsError(error, "Unable to add member.").message);
                }
              }}
            >
              Add member
            </Button>
          </div>
        ) : null}
      </SettingsDetailSection>

      <SettingsDetailSection id="owners" title="Owners">
        {ownerItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">No owners assigned.</p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border/70">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ownerItems.map((owner) => (
                  <TableRow key={owner.user_id}>
                    <TableCell>
                      <p className="font-medium text-foreground">{owner.display_name || owner.email}</p>
                      <p className="text-xs text-muted-foreground">{owner.email}</p>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={!canManage || removeOwnerMutation.isPending}
                        onClick={async () => {
                          setErrorMessage(null);
                          setSuccessMessage(null);
                          try {
                            await removeOwnerMutation.mutateAsync({ groupId: group.id, userId: owner.user_id });
                            setSuccessMessage("Owner removed.");
                          } catch (error) {
                            setErrorMessage(normalizeSettingsError(error, "Unable to remove owner.").message);
                          }
                        }}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {canManage && canViewUsers ? (
          <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
            <FormField label="Add owner">
              <Select value={ownerToAdd} onValueChange={setOwnerToAdd}>
                <SelectTrigger>
                  <SelectValue placeholder="Select user" />
                </SelectTrigger>
                <SelectContent>
                  {availableOwners.map((user) => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.display_name || user.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <Button
              disabled={!ownerToAdd || addOwnerMutation.isPending}
              onClick={async () => {
                setErrorMessage(null);
                setSuccessMessage(null);
                try {
                  await addOwnerMutation.mutateAsync({ groupId: group.id, userId: ownerToAdd });
                  setOwnerToAdd("");
                  setSuccessMessage("Owner added.");
                } catch (error) {
                  setErrorMessage(normalizeSettingsError(error, "Unable to add owner.").message);
                }
              }}
            >
              Add owner
            </Button>
          </div>
        ) : null}
      </SettingsDetailSection>

      <SettingsDetailSection id="lifecycle" title="Lifecycle" tone="danger">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">Deleting a group removes member and owner references.</p>
          <Button variant="destructive" disabled={!canManage || deleteMutation.isPending} onClick={() => setConfirmDeleteOpen(true)}>
            {deleteMutation.isPending ? "Deleting..." : "Delete group"}
          </Button>
        </div>
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave={canManage}
        disabledReason={canManage ? undefined : "You do not have permission to save group changes."}
        isSaving={updateMutation.isPending}
        onSave={() => {
          void saveChanges();
        }}
        onDiscard={() => {
          setDisplayName(group.display_name);
          setDescription(group.description || "");
          setMembershipMode(group.membership_mode);
          setIsActive(group.is_active);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Group changes are pending"
      />

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete group?"
        description={`Delete ${group.display_name}. This cannot be undone.`}
        confirmLabel="Delete"
        tone="danger"
        onCancel={() => setConfirmDeleteOpen(false)}
        onConfirm={async () => {
          setErrorMessage(null);
          setSuccessMessage(null);
          try {
            await deleteMutation.mutateAsync(group.id);
            navigate(listState.withCurrentSearch(settingsPaths.organization.groups), { replace: true });
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to delete group.").message);
          }
        }}
        isConfirming={deleteMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
