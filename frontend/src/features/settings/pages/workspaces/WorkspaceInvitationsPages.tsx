import { useMemo, useState } from "react";
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
import type { Invitation } from "@/api/invitations/api";
import type { WorkspaceProfile } from "@/types/workspaces";

import {
  normalizeSettingsError,
  useCancelWorkspaceInvitationMutation,
  useCreateWorkspaceInvitationMutation,
  useResendWorkspaceInvitationMutation,
  useWorkspaceInvitationDetailQuery,
  useWorkspaceInvitationsListQuery,
  useWorkspaceRolesListQuery,
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
  useSettingsErrorSummary,
  useSettingsListState,
} from "../../shared";

const SIMPLE_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function hasWorkspacePermission(workspace: WorkspaceProfile, permission: string) {
  return workspace.permissions.some((entry) => entry.toLowerCase() === permission.toLowerCase());
}

function workspaceBreadcrumbs(workspace: WorkspaceProfile, section: string) {
  return [
    { label: "Settings", href: settingsPaths.home },
    { label: "Workspaces", href: settingsPaths.workspaces.list },
    { label: workspace.name, href: settingsPaths.workspaces.general(workspace.id) },
    { label: section },
  ] as const;
}

function extractRoleIds(invitation: Invitation) {
  const workspaceContext = invitation.workspaceContext;
  if (!workspaceContext || typeof workspaceContext !== "object") {
    return [];
  }
  if (!Array.isArray(workspaceContext.roleAssignments)) {
    return [];
  }
  return workspaceContext.roleAssignments
    .map((entry) => entry.roleId)
    .filter((value): value is string => typeof value === "string");
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

const WORKSPACE_INVITATION_CREATE_SECTIONS = [
  { id: "invite-user", label: "Invite user" },
  { id: "initial-role-assignments", label: "Initial role assignments" },
] as const;

const WORKSPACE_INVITATION_DETAIL_SECTIONS = [
  { id: "invitation-details", label: "Invitation details" },
  { id: "seeded-roles", label: "Seeded roles" },
  { id: "actions", label: "Actions", tone: "danger" as const },
] as const;

export function WorkspaceInvitationsListPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState({
    defaults: { pageSize: 25 },
    filterKeys: ["status"],
  });
  const statusFilter = (listState.state.filters.status as "all" | Invitation["status"] | undefined) ?? "all";

  const canView =
    hasWorkspacePermission(workspace, "workspace.invitations.read") ||
    hasWorkspacePermission(workspace, "workspace.invitations.manage");
  const canManage = hasWorkspacePermission(workspace, "workspace.invitations.manage");

  const invitationsQuery = useWorkspaceInvitationsListQuery(workspace.id, {
    page: listState.state.page,
    pageSize: listState.state.pageSize,
    q: listState.state.q,
    status: statusFilter,
  });
  const rolesQuery = useWorkspaceRolesListQuery(workspace.id);

  const roleNamesById = useMemo(() => {
    const map = new Map<string, string>();
    for (const role of rolesQuery.data?.items ?? []) {
      map.set(role.id, role.name);
    }
    return map;
  }, [rolesQuery.data?.items]);

  const invitationItems = invitationsQuery.data?.items ?? [];
  const totalCount =
    typeof invitationsQuery.data?.meta.totalCount === "number"
      ? invitationsQuery.data.meta.totalCount
      : invitationItems.length;

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
  }

  return (
    <SettingsListLayout
      title="Invitations"
      subtitle="Track pending, accepted, and canceled workspace invitations."
      breadcrumbs={workspaceBreadcrumbs(workspace, "Invitations")}
      actions={
        canManage ? (
          <Button asChild>
            <Link to={listState.withCurrentSearch(settingsPaths.workspaces.invitationsCreate(workspace.id))}>
              Create invitation
            </Link>
          </Button>
        ) : null
      }
      commandBar={
        <SettingsCommandBar
          searchValue={listState.state.q}
          onSearchValueChange={listState.setQuery}
          searchPlaceholder="Search invitations"
          controls={
            <Select
              value={statusFilter}
              onValueChange={(value) => listState.setFilter("status", value === "all" ? null : value)}
            >
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="accepted">Accepted</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          }
        />
      }
    >
      {invitationsQuery.isLoading ? <LoadingState title="Loading invitations" className="min-h-[220px]" /> : null}
      {invitationsQuery.isError ? (
        <SettingsErrorState
          title="Unable to load invitations"
          message={normalizeSettingsError(invitationsQuery.error, "Unable to load workspace invitations.").message}
        />
      ) : null}
      {invitationsQuery.isSuccess && invitationItems.length === 0 ? (
        <SettingsEmptyState
          title="No invitations"
          description="Create an invitation to onboard a workspace principal."
          action={
            canManage ? (
              <Button asChild size="sm">
                <Link to={listState.withCurrentSearch(settingsPaths.workspaces.invitationsCreate(workspace.id))}>Create invitation</Link>
              </Button>
            ) : null
          }
        />
      ) : null}
      {invitationsQuery.isSuccess && invitationItems.length > 0 ? (
        <SettingsDataTable
          rows={invitationItems}
          columns={[
            {
              id: "email",
              header: "Email",
              cell: (invitation) => (
                <p className="font-medium text-foreground">{invitation.email_normalized}</p>
              ),
            },
            {
              id: "status",
              header: "Status",
              cell: (invitation) => (
                <Badge variant={invitation.status === "pending" ? "secondary" : "outline"}>
                  {invitation.status}
                </Badge>
              ),
            },
            {
              id: "roles",
              header: "Initial roles",
              cell: (invitation) => {
                const roleNames = extractRoleIds(invitation).map((roleId) => roleNamesById.get(roleId) ?? roleId);
                return <p className="text-muted-foreground">{roleNames.join(", ") || "No roles"}</p>;
              },
            },
            {
              id: "expires",
              header: "Expires",
              cell: (invitation) => <p className="text-muted-foreground">{formatDateTime(invitation.expires_at)}</p>,
            },
          ]}
          getRowId={(invitation) => invitation.id}
          onRowOpen={(invitation) =>
            navigate(
              listState.withCurrentSearch(settingsPaths.workspaces.invitationDetail(workspace.id, invitation.id)),
            )
          }
          page={listState.state.page}
          pageSize={listState.state.pageSize}
          totalCount={totalCount}
          onPageChange={listState.setPage}
          onPageSizeChange={listState.setPageSize}
          focusStorageKey={`settings-workspace-invitations-${workspace.id}`}
          rowsAreCurrentPage
        />
      ) : null}
    </SettingsListLayout>
  );
}

export function WorkspaceInvitationCreatePage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState();
  const canManage = hasWorkspacePermission(workspace, "workspace.invitations.manage");

  const rolesQuery = useWorkspaceRolesListQuery(workspace.id);
  const createMutation = useCreateWorkspaceInvitationMutation(workspace.id);

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const errorSummary = useSettingsErrorSummary({
    fieldIdByKey: {
      invitedUserEmail: "workspace-invite-email",
      displayName: "workspace-invite-display-name",
    },
    fieldLabelByKey: {
      invitedUserEmail: "Email",
      displayName: "Display name",
    },
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.invitations(workspace.id)} />;
  }

  return (
    <SettingsDetailLayout
      title="Create invitation"
      subtitle="Invite a user to this workspace and seed initial role assignments."
      breadcrumbs={[
        ...workspaceBreadcrumbs(workspace, "Invitations"),
        { label: "Create" },
      ]}
      actions={
        <Button
          variant="outline"
          onClick={() => navigate(listState.withCurrentSearch(settingsPaths.workspaces.invitations(workspace.id)))}
        >
          Cancel
        </Button>
      }
      sections={WORKSPACE_INVITATION_CREATE_SECTIONS}
      defaultSectionId="invite-user"
    >
      <SettingsFormErrorSummary summary={errorSummary.summary} />
      <SettingsFeedbackRegion
        messages={errorMessage ? [{ tone: "danger", message: errorMessage }] : []}
      />

      <SettingsDetailSection id="invite-user" title="Invite user">
        <FormField label="Email" required error={errorSummary.getFieldError("invitedUserEmail")}>
          <Input
            id="workspace-invite-email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="user@example.com"
          />
        </FormField>
        <FormField label="Display name" error={errorSummary.getFieldError("displayName")}>
          <Input
            id="workspace-invite-display-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Optional"
          />
        </FormField>
      </SettingsDetailSection>

      <SettingsDetailSection id="initial-role-assignments" title="Initial role assignments">
        {rolesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading workspace roles...</p>
        ) : (
          <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
            {(rolesQuery.data?.items ?? []).map((role) => {
              const checked = selectedRoleIds.includes(role.id);
              const checkboxId = `workspace-invite-role-${role.id}`;
              return (
                <div key={role.id} className="flex items-start gap-2 text-sm">
                  <input
                    id={checkboxId}
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => {
                      const nextChecked = event.target.checked;
                      setSelectedRoleIds((current) => {
                        if (nextChecked) {
                          return current.includes(role.id) ? current : [...current, role.id];
                        }
                        return current.filter((value) => value !== role.id);
                      });
                    }}
                  />
                  <label htmlFor={checkboxId}>
                    <span className="font-medium text-foreground">{role.name}</span>
                    <span className="block text-xs text-muted-foreground">{role.description || role.slug}</span>
                  </label>
                </div>
              );
            })}
          </div>
        )}
      </SettingsDetailSection>

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => navigate(listState.withCurrentSearch(settingsPaths.workspaces.invitations(workspace.id)))}
        >
          Cancel
        </Button>
        <Button
          disabled={createMutation.isPending}
          onClick={async () => {
            setErrorMessage(null);
            errorSummary.clearErrors();
            const normalizedEmail = email.trim().toLowerCase();
            if (!SIMPLE_EMAIL_PATTERN.test(normalizedEmail)) {
              errorSummary.setClientErrors({ invitedUserEmail: "Enter a valid email address." });
              setErrorMessage("Please review the highlighted fields.");
              return;
            }

            try {
              const created = await createMutation.mutateAsync({
                invitedUserEmail: normalizedEmail,
                displayName: displayName.trim() || null,
                workspaceContext: {
                  workspaceId: workspace.id,
                  roleAssignments: selectedRoleIds.map((roleId) => ({ roleId })),
                },
              });
              navigate(
                listState.withCurrentSearch(settingsPaths.workspaces.invitationDetail(workspace.id, created.id)),
                { replace: true },
              );
            } catch (error) {
              const normalized = normalizeSettingsError(error, "Unable to create invitation.");
              setErrorMessage(normalized.message);
              errorSummary.setProblemErrors(normalized.fieldErrors);
            }
          }}
        >
          {createMutation.isPending ? "Creating..." : "Send invitation"}
        </Button>
      </div>
    </SettingsDetailLayout>
  );
}

export function WorkspaceInvitationDetailPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const { invitationId } = useParams<{ invitationId: string }>();

  const canView =
    hasWorkspacePermission(workspace, "workspace.invitations.read") ||
    hasWorkspacePermission(workspace, "workspace.invitations.manage");
  const canManage = hasWorkspacePermission(workspace, "workspace.invitations.manage");

  const detailQuery = useWorkspaceInvitationDetailQuery(workspace.id, invitationId ?? null);
  const rolesQuery = useWorkspaceRolesListQuery(workspace.id);
  const resendMutation = useResendWorkspaceInvitationMutation(workspace.id);
  const cancelMutation = useCancelWorkspaceInvitationMutation(workspace.id);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);

  const roleNamesById = useMemo(() => {
    const map = new Map<string, string>();
    for (const role of rolesQuery.data?.items ?? []) {
      map.set(role.id, role.name);
    }
    return map;
  }, [rolesQuery.data?.items]);

  if (!canView) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.invitations(workspace.id)} />;
  }

  if (detailQuery.isLoading) {
    return <LoadingState title="Loading invitation" className="min-h-[300px]" />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <SettingsErrorState
        title="Invitation unavailable"
        message={normalizeSettingsError(detailQuery.error, "Unable to load invitation details.").message}
      />
    );
  }

  const invitation = detailQuery.data;
  const roleNames = extractRoleIds(invitation).map((roleId) => roleNamesById.get(roleId) ?? roleId);
  const canMutate =
    canManage &&
    (invitation.status === "pending" || invitation.status === "expired");

  return (
    <SettingsDetailLayout
      title={invitation.email_normalized}
      subtitle="Review invitation lifecycle and perform pending invitation actions."
      breadcrumbs={[
        ...workspaceBreadcrumbs(workspace, "Invitations"),
        { label: invitation.email_normalized },
      ]}
      actions={<Badge variant={invitation.status === "pending" ? "secondary" : "outline"}>{invitation.status}</Badge>}
      sections={WORKSPACE_INVITATION_DETAIL_SECTIONS}
      defaultSectionId="invitation-details"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      <SettingsDetailSection id="invitation-details" title="Invitation details">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Invited email</p>
            <p className="text-sm text-foreground">{invitation.email_normalized}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Invited by</p>
            <p className="text-sm text-foreground">{invitation.invited_by_user_id}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Created</p>
            <p className="text-sm text-foreground">{formatDateTime(invitation.created_at)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Expires</p>
            <p className="text-sm text-foreground">{formatDateTime(invitation.expires_at)}</p>
          </div>
        </div>
      </SettingsDetailSection>

      <SettingsDetailSection id="seeded-roles" title="Seeded roles">
        <p className="text-sm text-muted-foreground">{roleNames.join(", ") || "No seeded roles"}</p>
      </SettingsDetailSection>

      <SettingsDetailSection id="actions" title="Actions" tone="danger">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={!canMutate || resendMutation.isPending}
            onClick={async () => {
              setErrorMessage(null);
              setSuccessMessage(null);
              try {
                await resendMutation.mutateAsync(invitation.id);
                setSuccessMessage("Invitation resent.");
              } catch (error) {
                setErrorMessage(normalizeSettingsError(error, "Unable to resend invitation.").message);
              }
            }}
          >
            {resendMutation.isPending ? "Resending..." : "Resend invitation"}
          </Button>
          <Button variant="destructive" disabled={!canMutate || cancelMutation.isPending} onClick={() => setConfirmCancelOpen(true)}>
            {cancelMutation.isPending ? "Cancelling..." : "Cancel invitation"}
          </Button>
        </div>
      </SettingsDetailSection>

      <ConfirmDialog
        open={confirmCancelOpen}
        title="Cancel invitation?"
        description="The recipient will no longer be able to redeem this invitation."
        confirmLabel="Cancel invitation"
        tone="danger"
        onCancel={() => setConfirmCancelOpen(false)}
        onConfirm={async () => {
          setErrorMessage(null);
          setSuccessMessage(null);
          try {
            await cancelMutation.mutateAsync(invitation.id);
            setConfirmCancelOpen(false);
            setSuccessMessage("Invitation canceled.");
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to cancel invitation.").message);
          }
        }}
        isConfirming={cancelMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
