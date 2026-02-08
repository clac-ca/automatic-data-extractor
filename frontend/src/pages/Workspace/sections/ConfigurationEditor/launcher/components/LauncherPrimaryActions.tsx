import { FilePlus2, FolderOpen, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";

interface LauncherPrimaryActionsProps {
  readonly workspaceName: string;
  readonly activeConfigurationName?: string | null;
  readonly isCreatingDraft: boolean;
  readonly isImporting: boolean;
  readonly onCreateDraft: () => void;
  readonly onImportConfiguration: () => void;
  readonly onOpenActiveConfiguration: () => void;
}

export function LauncherPrimaryActions({
  workspaceName,
  activeConfigurationName,
  isCreatingDraft,
  isImporting,
  onCreateDraft,
  onImportConfiguration,
  onOpenActiveConfiguration,
}: LauncherPrimaryActionsProps) {
  const hasActiveConfiguration = Boolean(activeConfigurationName);

  return (
    <section className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Configuration launcher
        </p>
        <h1 className="text-xl font-semibold text-foreground">Open a configuration</h1>
        <p className="text-sm text-muted-foreground">
          Create or import a draft, then continue editing in the workbench.
        </p>
      </div>

      <div className="grid gap-3">
        <Button
          type="button"
          className="h-10 justify-start gap-2"
          onClick={onCreateDraft}
          isLoading={isCreatingDraft}
        >
          <FilePlus2 className="h-4 w-4" />
          New configuration
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="h-10 justify-start gap-2"
          onClick={onImportConfiguration}
          isLoading={isImporting}
        >
          <Upload className="h-4 w-4" />
          Import configuration (.zip)
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 justify-start gap-2"
          onClick={onOpenActiveConfiguration}
          disabled={!hasActiveConfiguration}
          title={
            hasActiveConfiguration
              ? `Open active configuration ${activeConfigurationName}`
              : "No active configuration in this workspace"
          }
        >
          <FolderOpen className="h-4 w-4" />
          Open active configuration
        </Button>
      </div>

      <div className="rounded-lg border border-border/70 bg-muted/20 p-3 text-xs text-muted-foreground">
        Workspace: <span className="font-medium text-foreground">{workspaceName.trim() || "Workspace"}</span>
      </div>
    </section>
  );
}
