import { Link } from "react-router-dom";

import { ConfigureIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { buildConfigurationsPath } from "@/pages/Workspace/sections/ConfigurationEditor/paths";

export function DocumentsConfigBanner({ workspaceId }: { workspaceId: string }) {
  return (
    <div
      role="status"
      className="mb-3 flex flex-col gap-3 rounded-lg border border-accent/60 bg-accent/40 px-4 py-3 text-sm text-accent-foreground sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-accent-foreground/80">
          <ConfigureIcon className="h-5 w-5" />
        </span>
        <div>
          <p className="font-semibold">No active configuration</p>
          <p className="text-sm text-accent-foreground/80">
            Uploads will queue until a configuration is active.
          </p>
        </div>
      </div>
      <Button asChild size="sm" variant="outline" className="shrink-0">
        <Link to={buildConfigurationsPath(workspaceId)}>Create configuration</Link>
      </Button>
    </div>
  );
}
