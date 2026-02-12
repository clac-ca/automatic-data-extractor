import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageState } from "@/components/layout";

import { settingsPaths } from "../routing/contracts";

export function SettingsHomePage({
  canAccessOrganization,
  hasWorkspaceAccess,
  defaultWorkspaceId,
}: {
  readonly canAccessOrganization: boolean;
  readonly hasWorkspaceAccess: boolean;
  readonly defaultWorkspaceId: string | null;
}) {
  if (!canAccessOrganization && !hasWorkspaceAccess) {
    return (
      <PageState
        variant="empty"
        title="No settings access"
        description="You do not currently have permission to organization or workspace settings."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border/70 bg-background p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Admin console</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">Settings overview</h2>
        <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
          Manage organization identity and workspace operations in one place. Only sections you can administer are shown.
        </p>
      </section>

      {canAccessOrganization ? (
        <section className="rounded-2xl border border-border/70 bg-background p-8 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Organization</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Organization settings</h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Manage users, groups, role definitions, API keys, authentication policy, and run controls.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
            <Badge variant="secondary">Global administration</Badge>
            <Button asChild size="sm">
              <Link to={settingsPaths.organization.users}>Open organization</Link>
            </Button>
          </div>
        </section>
      ) : null}

      {hasWorkspaceAccess ? (
        <section className="rounded-2xl border border-border/70 bg-background p-8 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Workspaces</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Workspace settings</h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Open a workspace to manage processing, access principals, invitations, and lifecycle controls.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
            <Badge variant="secondary">Scoped administration</Badge>
            <Button asChild size="sm">
              <Link
                to={
                  defaultWorkspaceId
                    ? settingsPaths.workspaces.general(defaultWorkspaceId)
                    : settingsPaths.workspaces.list
                }
              >
                Open workspaces
              </Link>
            </Button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
