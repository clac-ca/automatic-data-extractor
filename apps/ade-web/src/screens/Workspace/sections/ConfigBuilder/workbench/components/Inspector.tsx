import type { WorkbenchFileTab } from "../types";

interface InspectorProps {
  readonly width: number;
  readonly file: WorkbenchFileTab | null;
}

export function Inspector({ width, file }: InspectorProps) {
  if (!file) {
    return null;
  }
  const isDirty = file.status === "ready" && file.content !== file.initialContent;
  const metadata = file.metadata;

  return (
    <aside className="flex h-full min-h-0 flex-shrink-0 flex-col border-l border-slate-200 bg-slate-50" style={{ width }}>
      <header className="border-b border-slate-200 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Inspector</h2>
      </header>
      <div className="flex-1 space-y-4 overflow-auto px-3 py-4 text-sm text-slate-600">
        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">File</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Name</dt>
              <dd className="text-slate-700">{file.name}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Path</dt>
              <dd className="break-words text-slate-700">{file.id}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Language</dt>
              <dd className="text-slate-700">{file.language ?? "plain text"}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">Metadata</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Size</dt>
              <dd className="text-slate-700">{formatFileSize(metadata?.size)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Last modified</dt>
              <dd className="text-slate-700">{formatTimestamp(metadata?.modifiedAt)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Content type</dt>
              <dd className="text-slate-700">{metadata?.contentType ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">ETag</dt>
              <dd className="break-words text-slate-700">{metadata?.etag ?? "—"}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">Editor</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Load status</dt>
              <dd className="text-slate-700 capitalize">{file.status}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Dirty</dt>
              <dd className="text-slate-700">{isDirty ? "Yes" : "No"}</dd>
            </div>
          </dl>
        </section>

        <p className="text-xs leading-relaxed text-slate-500">
          The inspector stays in sync with the active tab. Future work can hydrate this panel with schema-aware helpers and
          quick actions without reworking the layout.
        </p>
      </div>
    </aside>
  );
}

function formatFileSize(size: number | null | undefined): string {
  if (size == null) {
    return "—";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = size / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`;
}

function formatTimestamp(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "—";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}
