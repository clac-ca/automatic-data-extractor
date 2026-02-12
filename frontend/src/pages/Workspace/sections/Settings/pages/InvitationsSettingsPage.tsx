import { useState } from "react";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
  const resendInvitation = useResendWorkspaceInvitationMutation(workspace.id);
  const cancelInvitation = useCancelWorkspaceInvitationMutation(workspace.id);

  const [feedback, setFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null);

  if (!canReadInvitations) {
    return <Alert tone="danger">You do not have permission to access workspace invitations.</Alert>;
  }

  const invitations = invitationsQuery.data?.items ?? [];

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
            : `${invitations.length} invitation${invitations.length === 1 ? "" : "s"}`
        }
      >
        {invitationsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading invitations...</p>
        ) : invitations.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No invitations yet.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <Table>
              <TableHeader>
                <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <TableHead className="px-4">Email</TableHead>
                  <TableHead className="px-4">Status</TableHead>
                  <TableHead className="px-4">Expires</TableHead>
                  <TableHead className="px-4 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invitations.map((invitation) => (
                  <TableRow key={invitation.id}>
                    <TableCell className="px-4 py-3 font-medium">{invitation.email_normalized}</TableCell>
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
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={!canManageInvitations || resendInvitation.isPending}
                          onClick={async () => {
                            setFeedback(null);
                            try {
                              await resendInvitation.mutateAsync(invitation.id);
                              setFeedback({ tone: "success", message: "Invitation resent." });
                            } catch (error) {
                              setFeedback({
                                tone: "danger",
                                message:
                                  error instanceof Error ? error.message : "Unable to resend invitation.",
                              });
                            }
                          }}
                        >
                          Resend
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={!canManageInvitations || cancelInvitation.isPending}
                          onClick={async () => {
                            setFeedback(null);
                            try {
                              await cancelInvitation.mutateAsync(invitation.id);
                              setFeedback({ tone: "success", message: "Invitation canceled." });
                            } catch (error) {
                              setFeedback({
                                tone: "danger",
                                message:
                                  error instanceof Error ? error.message : "Unable to cancel invitation.",
                              });
                            }
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </SettingsSection>
    </div>
  );
}
