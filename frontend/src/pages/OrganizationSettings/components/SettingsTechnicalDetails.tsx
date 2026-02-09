import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";

import type { AdminSettingsReadResponse } from "@/api/admin/settings";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { collectLockedEnvVars, formatRuntimeSettingsTimestamp } from "./runtimeSettingsUtils";

export function SettingsTechnicalDetails({
  settings,
  isLoading = false,
  onRefresh,
}: {
  readonly settings?: AdminSettingsReadResponse;
  readonly isLoading?: boolean;
  readonly onRefresh?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const lockedEnvVars = useMemo(
    () => (settings ? collectLockedEnvVars(settings) : []),
    [settings],
  );

  if (!settings && !isLoading) {
    return null;
  }

  return (
    <section className="rounded-xl border border-border/70 bg-muted/10 p-4">
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-foreground">Technical details</p>
            <p className="text-xs text-muted-foreground">
              {isLoading && !settings ? "Loading metadata..." : "Schema version, revision, and environment lock context."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {onRefresh ? (
              <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
                Refresh
              </Button>
            ) : null}
            <CollapsibleTrigger asChild>
              <Button type="button" variant="outline" size="sm" className="gap-1.5">
                {open ? "Hide details" : "Show details"}
                <ChevronDown className={["h-4 w-4 transition-transform", open ? "rotate-180" : ""].join(" ")} />
              </Button>
            </CollapsibleTrigger>
          </div>
        </div>

        <CollapsibleContent className="pt-4">
          {settings ? (
            <div className="space-y-4 text-sm">
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2">
                <dt className="text-muted-foreground">Schema version</dt>
                <dd className="font-medium text-foreground">{settings.schemaVersion}</dd>
                <dt className="text-muted-foreground">Revision</dt>
                <dd className="font-medium text-foreground">{settings.revision}</dd>
                <dt className="text-muted-foreground">Updated</dt>
                <dd className="font-medium text-foreground">{formatRuntimeSettingsTimestamp(settings.updatedAt)}</dd>
                <dt className="text-muted-foreground">Updated by</dt>
                <dd className="font-medium text-foreground">{settings.updatedBy ?? "System"}</dd>
              </dl>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Environment-managed fields
                </p>
                {lockedEnvVars.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No fields are currently locked by environment variables.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {lockedEnvVars.map((envVar) => (
                      <Badge key={envVar} variant="outline" className="border-warning/40 bg-warning/10 text-warning-foreground">
                        {envVar}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
