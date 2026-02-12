import { useEffect, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createGroup,
  deleteGroup,
  listGroupMembers,
  listGroups,
  updateGroup,
  type Group,
} from "@/api/groups/api";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SettingsDrawer } from "@/pages/Workspace/sections/Settings/components/SettingsDrawer";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
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
  const canReadMembers = hasPermission("groups.members.read_all") || canManageGroups;

  const groupsQuery = useGroupsQuery(canReadGroups);
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

  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);
  const selectedParam = params[0];
  const isCreateOpen = selectedParam === "new";
  const selectedGroupId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const groups = groupsQuery.data?.items ?? [];
  const selectedGroup = groups.find((group) => group.id === selectedGroupId);

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
      <SettingsSection
        title="Groups"
        description={
          groupsQuery.isLoading ? "Loading groups..." : `${groups.length} group${groups.length === 1 ? "" : "s"}`
        }
        actions={
          canManageGroups ? (
            <Button type="button" size="sm" onClick={openCreateDrawer}>
              Create group
            </Button>
          ) : null
        }
      >
        {groupsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading groups...</p>
        ) : groups.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No groups found.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <Table>
              <TableHeader>
                <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <TableHead className="px-4">Group</TableHead>
                  <TableHead className="px-4">Type</TableHead>
                  <TableHead className="px-4">Status</TableHead>
                  <TableHead className="px-4 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {groups.map((group) => (
                  <TableRow key={group.id}>
                    <TableCell className="px-4 py-3">
                      <p className="font-semibold text-foreground">{group.display_name}</p>
                      <p className="text-xs text-muted-foreground">{group.slug}</p>
                    </TableCell>
                    <TableCell className="px-4 py-3">
                      <Badge variant="outline">{group.membership_mode}</Badge>
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
        )}
      </SettingsSection>

      <GroupDrawer
        open={isCreateOpen && canManageGroups}
        mode="create"
        canReadMembers={canReadMembers}
        onClose={closeDrawer}
        onSave={async (payload) => {
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
        canManage={canManageGroups}
        onClose={closeDrawer}
        onSave={async (payload) => {
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
        isSaving={updateGroupMutation.isPending}
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
  onClose,
  onSave,
  onDelete,
  isSaving,
  isDeleting = false,
}: {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly group?: Group;
  readonly canManage?: boolean;
  readonly canReadMembers: boolean;
  readonly onClose: () => void;
  readonly onSave: (payload: {
    display_name?: string;
    slug?: string;
    description?: string | null;
    membership_mode?: "assigned" | "dynamic";
    is_active?: boolean;
  }) => Promise<void>;
  readonly onDelete?: () => Promise<void>;
  readonly isSaving: boolean;
  readonly isDeleting?: boolean;
}) {
  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const membersQuery = useQuery({
    queryKey: ["organization", "groups", group?.id, "members"],
    queryFn: () => listGroupMembers(group!.id),
    enabled: open && canReadMembers && Boolean(group?.id),
    staleTime: 10_000,
  });

  useEffect(() => {
    if (!open) {
      setError(null);
      return;
    }
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!displayName.trim()) {
      setError("Group display name is required.");
      return;
    }
    try {
      if (mode === "create") {
        await onSave({
          display_name: displayName.trim(),
          slug: slug.trim() || undefined,
          description: description.trim() || null,
          membership_mode: "assigned",
        });
      } else {
        await onSave({
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
        <FormField label="Display name" required>
          <Input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Analytics Team"
            disabled={!canManage || isSaving}
          />
        </FormField>
        {mode === "create" ? (
          <FormField label="Slug">
            <Input
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              placeholder="analytics-team"
              disabled={!canManage || isSaving}
            />
          </FormField>
        ) : null}
        <FormField label="Description">
          <Input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Optional"
            disabled={!canManage || isSaving}
          />
        </FormField>
        {mode === "edit" && canReadMembers ? (
          <div className="rounded-lg border border-border p-3">
            <p className="text-sm font-semibold">Members</p>
            {membersQuery.isLoading ? (
              <p className="text-xs text-muted-foreground">Loading members...</p>
            ) : (membersQuery.data?.items.length ?? 0) === 0 ? (
              <p className="text-xs text-muted-foreground">No direct members.</p>
            ) : (
              <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                {membersQuery.data?.items.map((member) => (
                  <p key={member.user_id}>{member.display_name ?? member.email ?? member.user_id}</p>
                ))}
              </div>
            )}
          </div>
        ) : null}
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
