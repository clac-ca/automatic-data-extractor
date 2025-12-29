import { Button } from "@ui/Button";

export function RunsHeader({ onExport, onStartRun }: { onExport: () => void; onStartRun: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Runs</p>
        <h1 className="text-2xl font-semibold text-foreground">Run operations</h1>
        <p className="text-sm text-muted-foreground">
          Scan results, open run details, and drill into quality issues in one place.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onExport}>Export</Button>
        <Button onClick={onStartRun}>Start run</Button>
      </div>
    </div>
  );
}
