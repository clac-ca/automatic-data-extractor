import { useState } from "react";
import clsx from "clsx";

import { Button } from "@ui/Button";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import { RUN_STATUS_META } from "../constants";
import { formatNumber, formatQuality } from "../utils";
import type { RunRecord } from "../types";

type InspectorTab = "summary" | "metrics" | "fields" | "columns";

export function RunPreviewPanel({ run, onClose }: { run: RunRecord; onClose?: () => void }) {
  const [tab, setTab] = useState<InspectorTab>("summary");
  const warningsLabel =
    run.warnings === null ? "Warnings data unavailable" : `${formatNumber(run.warnings)} warnings detected`;
  const errorsLabel =
    run.errors === null ? "Errors data unavailable" : `${formatNumber(run.errors)} errors detected`;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span
            className={clsx(
              "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
              RUN_STATUS_META[run.status].badgeClass,
            )}
          >
            {RUN_STATUS_META[run.status].label}
          </span>
          <h3 className="mt-2 text-base font-semibold text-foreground">{run.inputName}</h3>
          <p className="text-xs text-muted-foreground">{run.id}</p>
        </div>
        <div className="flex items-start gap-3 text-xs text-muted-foreground">
          <div>
            <p>{run.startedAtLabel}</p>
            <p>{run.durationLabel}</p>
          </div>
          {onClose ? (
            <Button size="sm" variant="ghost" onClick={onClose}>
              Close preview
            </Button>
          ) : null}
        </div>
      </div>

      <TabsRoot value={tab} onValueChange={(value) => setTab(value as InspectorTab)}>
        <TabsList className="mt-4 flex flex-wrap gap-2 border-b border-border pb-2">
          <TabButton value="summary" label="Summary" active={tab === "summary"} />
          <TabButton value="metrics" label="Metrics" active={tab === "metrics"} />
          <TabButton value="fields" label="Fields" active={tab === "fields"} />
          <TabButton value="columns" label="Columns" active={tab === "columns"} />
        </TabsList>

        <TabsContent value="summary" className="mt-4">
          <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
            <div>
              <div className="grid gap-2 sm:grid-cols-4">
                <MiniMetric label="Rows" value={formatNumber(run.rows)} />
                <MiniMetric label="Quality" value={formatQuality(run.quality ?? null)} />
                <MiniMetric label="Warnings" value={formatNumber(run.warnings)} />
                <MiniMetric label="Errors" value={formatNumber(run.errors)} />
              </div>
              <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                <DetailRow label="Output" value={run.outputName ?? "Output not available"} />
                <DetailRow label="Config" value={run.configLabel} />
                <DetailRow label="Trigger" value={run.triggerLabel} />
                <DetailRow label="Engine" value={run.engineLabel} />
                <DetailRow label="Region" value={run.regionLabel} />
                <DetailRow label="Owner" value={run.ownerLabel} />
              </div>
            </div>
            <div className="rounded-xl border border-border bg-background p-3">
              <h4 className="text-sm font-semibold text-foreground">Quick issues</h4>
              <ul className="mt-3 space-y-2 text-xs text-muted-foreground">
                <li className="rounded-lg border border-border bg-card px-2 py-2">{warningsLabel}</li>
                <li className="rounded-lg border border-border bg-card px-2 py-2">{errorsLabel}</li>
                <li className="rounded-lg border border-border bg-card px-2 py-2">
                  Notes: {run.notes ?? "No notes captured"}
                </li>
              </ul>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary">
                  View logs
                </Button>
                <Button size="sm" variant="ghost">
                  Open output
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="metrics" className="mt-4">
          <PlaceholderPanel
            title="Run metrics not available yet"
            description="Wire /api/v1/runs/{run_id}/metrics into the OpenAPI schema so we can populate this tab."
          />
        </TabsContent>

        <TabsContent value="fields" className="mt-4">
          <PlaceholderPanel
            title="Field mappings pending"
            description="Wire /api/v1/runs/{run_id}/fields into the OpenAPI schema to populate field coverage."
          />
        </TabsContent>

        <TabsContent value="columns" className="mt-4">
          <PlaceholderPanel
            title="Column mappings pending"
            description="Wire /api/v1/runs/{run_id}/columns into the OpenAPI schema to show detected headers."
          />
        </TabsContent>
      </TabsRoot>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
      <span>{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

function TabButton({ value, label, active }: { value: InspectorTab; label: string; active: boolean }) {
  return (
    <TabsTrigger
      value={value}
      className={clsx(
        "rounded-full border px-3 py-1 text-xs font-semibold transition",
        active ? "border-transparent bg-brand-600 text-on-brand" : "border-border bg-background text-muted-foreground",
      )}
    >
      {label}
    </TabsTrigger>
  );
}

function PlaceholderPanel({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-background px-4 py-4">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
    </div>
  );
}
