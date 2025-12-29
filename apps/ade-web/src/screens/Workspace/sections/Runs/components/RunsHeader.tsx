import { Button } from "@ui/Button";

export function RunsHeader({ onExport, onStartRun }: { onExport: () => void; onStartRun: () => void }) {
  return (
    <header className="shrink-0 border-b border-border bg-card">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-muted text-foreground">
            <RunIcon />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-foreground">Runs</h1>
            <p className="text-xs text-muted-foreground">Monitor execution health, output quality, and mapping coverage.</p>
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={onExport}>
            Export
          </Button>
          <Button onClick={onStartRun}>Start run</Button>
        </div>
      </div>
    </header>
  );
}

function RunIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M6 4.5v11l8.5-5.5L6 4.5Z" fill="currentColor" />
    </svg>
  );
}
