import { useMemo, useState } from "react";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { AccessCommandBar, AssignmentChips } from "@/pages/SharedAccess/components";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { MoreHorizontal } from "lucide-react";
import type { Invitation } from "@/api/invitations/api";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { SettingsSection } from "../components/SettingsSection";
import {
  useCancelWorkspaceInvitationMutation,
  useResendWorkspaceInvitationMutation,
  useWorkspaceInvitationsQuery,
} from "../hooks/useWorkspaceInvitations";

type FeedbackTone = "success" | "danger";

export function InvitationsSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const canManageInvitations = hasPermission("workspace.invitations.manage");
  const canReadInvitations = hasPermission("workspace.invitations.read") || canManageInvitations;

  const invitationsQuery = useWorkspaceInvitationsQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const resendInvitation = useResendWorkspaceInvitationMutation(workspace.id);
  const cancelInvitation = useCancelWorkspaceInvitationMutation(workspace.id);

  const [feedback, setFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null);
  const [searchValue, setSearchValue] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | Invitation["status"]>("all");
  const [selectedInvitationId, setSelectedInvitationId] = useState<string | null>(null);
  const [confirmCancelInvitationId, setConfirmCancelInvitationId] = useState<string | null>(null);

  const roleNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const role of rolesQuery.data?.items ?? []) {
      map.set(role.id, role.name);
    }
    return map;
  }, [rolesQuery.data?.items]);

  const invitations = invitationsQuery.data?.items ?? [];
  const filteredInvitations = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    return invitations.filter((invitation) => {
      if (statusFilter !== "all" && invitation.status !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      const roles = extractRoleIds(invitation).join(" ").toLowerCase();
      const haystack = `${invitation.email_normalized} ${invitation.invited_by_user_id} ${roles}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [invitations, searchValue, statusFilter]);

  const selectedInvitation =
    selectedInvitationId !== null
      ? invitations.find((invitation) => invitation.id === selectedInvitationId)
      : undefined;
  const cancelTarget =
    confirmCancelInvitationId !== null
      ? invitations.find((invitation) => invitation.id === confirmCancelInvitationId)
      : undefined;

  if (!canReadInvitations) {
    return <Alert tone="danger">You do not have permission to access workspace invitations.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {invitationsQuery.isError ? (
        <Alert tone="danger">
          {invitationsQuery.error instanceof Error
            ? invitationsQuery.error.message
            : "Unable to load workspace invitations."}
        </Alert>
      ) : null}

      <SettingsSection
        title="Workspace invitations"
        description={
          invitationsQuery.isLoading
            ? "Loading invitations..."
            : `${filteredInvitations.length} invitation${filteredInvitations.length === 1 ? "" : "s"}`
        }
      >
        <AccessCommandBar
          searchValue={searchValue}
          onSearchValueChange={setSearchValue}
          searchPlaceholder="Search invitations"
          searchAriaLabel="Search invitations"
          controls={
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter(value as "all" | Invitation["status"])}
            >
              <SelectTrigger className="w-full min-w-36 sm:w-44">
                <SelectValue placeholder="Filter status" />
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

        {invitationsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading invitations...</p>
        ) : filteredInvitations.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No invitations match your current filters.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <Table>
              <TableHeader>
                <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <TableHead className="px-4">Email</TableHead>
                  <TableHead className="px-4">Initial roles</TableHead>
                  <TableHead className="px-4">Inviter</TableHead>
                  <TableHead className="px-4">Status</TableHead>
                  <TableHead className="px-4">Expires</TableHead>
                  <TableHead className="px-4 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredInvitations.map((invitation) => {
                  const roleNames = extractRoleIds(invitation).map(
                    (roleId) => roleNameById.get(roleId) ?? roleId,
                  );
                  const canMutate = canManageInvitations && invitation.status === "pending";
                  const inviterLabel = invitation.invited_by_user_id;

                  return (
                    <TableRow key={invitation.id}>
                      <TableCell className="px-4 py-3 font-medium">{invitation.email_normalized}</TableCell>
                      <TableCell className="px-4 py-3">
                        <AssignmentChips assignments={roleNames} emptyLabel="No seeded roles" />
                      </TableCell>
                      <TableCell className="px-4 py-3 text-muted-foreground">{inviterLabel}</TableCell>
                      <TableCell className="px-4 py-3">
                        <Badge variant={invitation.status === "pending" ? "secondary" : "outline"}>
                          {invitation.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="px-4 py-3 text-muted-foreground">
                        {invitation.expires_at
                          ? new Date(invitation.expires_at).toLocaleString()
                          : "No expiry"}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button type="button" variant="ghost" size="icon" aria-label="Invitation actions">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setSelectedInvitationId(invitation.id)}>
                              View details
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={!canMutate || resendInvitation.isPending}
                              onClick={async () => {
                                setFeedback(null);
                                try {
                                  await resendInvitation.mutateAsync(invitation.id);
                                  setFeedback({ tone: "success", message: "Invitation resent." });
                                } catch (error) {
                                  setFeedback({
                                    tone: "danger",
                                    message:
                                      error instanceof Error
                                        ? error.message
                                        : "Unable to resend invitation.",
                                  });
                                }
                              }}
                            >
                              Resend invitation
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={!canMutate || cancelInvitation.isPending}
                              onClick={() => setConfirmCancelInvitationId(invitation.id)}
                            >
                              Cancel invitation
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </SettingsSection>

      <SettingsDrawer
        open={Boolean(selectedInvitation)}
        onClose={() => setSelectedInvitationId(null)}
        title={selectedInvitation ? `Invitation: ${selectedInvitation.email_normalized}` : "Invitation"}
        description="Review invitation metadata, seeded roles, and lifecycle timestamps."
      >
        {selectedInvitation ? (
          <div className="space-y-4">
            <div className="grid gap-3 rounded-lg border border-border bg-background p-4 text-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</p>
                <Badge variant={selectedInvitation.status === "pending" ? "secondary" : "outline"}>
                  {selectedInvitation.status}
                </Badge>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Inviter</p>
                <p className="text-foreground">
                  {selectedInvitation.invited_by_user_id}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Initial roles</p>
                <AssignmentChips
                  assignments={extractRoleIds(selectedInvitation).map(
                    (roleId) => roleNameById.get(roleId) ?? roleId,
                  )}
                  emptyLabel="No seeded roles"
                />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Created</p>
                <p className="text-foreground">{new Date(selectedInvitation.created_at).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Expires</p>
                <p className="text-foreground">
                  {selectedInvitation.expires_at
                    ? new Date(selectedInvitation.expires_at).toLocaleString()
                    : "No expiry"}
                </p>
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="button" variant="ghost" onClick={() => setSelectedInvitationId(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </SettingsDrawer>

      <ConfirmDialog
        open={Boolean(cancelTarget)}
        title="Cancel invitation?"
        description={
          cancelTarget
            ? `Cancel invitation for ${cancelTarget.email_normalized}. The recipient will no longer be able to redeem it.`
            : ""
        }
        confirmLabel="Cancel invitation"
        tone="danger"
        onCancel={() => setConfirmCancelInvitationId(null)}
        onConfirm={async () => {
          if (!cancelTarget) {
            return;
          }
          setFeedback(null);
          try {
            await cancelInvitation.mutateAsync(cancelTarget.id);
            setFeedback({ tone: "success", message: "Invitation canceled." });
            setConfirmCancelInvitationId(null);
          } catch (error) {
            setFeedback({
              tone: "danger",
              message: error instanceof Error ? error.message : "Unable to cancel invitation.",
            });
          }
        }}
        isConfirming={cancelInvitation.isPending}
      />
    </div>
  );
}

function extractRoleIds(invitation: Invitation): string[] {
  const roleAssignments =
    invitation.metadata && typeof invitation.metadata === "object"
      ? (invitation.metadata as Record<string, unknown>).roleAssignments
      : null;
  if (!Array.isArray(roleAssignments)) {
    return [];
  }

  return roleAssignments
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const roleId = (item as Record<string, unknown>).roleId;
      return typeof roleId === "string" && roleId.length > 0 ? roleId : null;
    })
    .filter((item): item is string => item !== null);
}
