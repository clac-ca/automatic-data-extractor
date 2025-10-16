import type { DocumentRow } from "../utils";
import { formatDateTime, formatFileSize, formatStatusLabel } from "../utils";

interface DocumentDetailsProps {
  readonly document: DocumentRow;
}

export function DocumentDetails({ document }: DocumentDetailsProps) {
  return (
    <div className="flex flex-col gap-6 text-sm text-slate-600">
      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Document</h3>
        <dl className="space-y-2">
          <Detail term="Name" value={document.name} />
          <Detail term="Status" value={formatStatusLabel(document.status)} />
          <Detail term="Source" value={document.source} />
          <Detail term="Uploaded" value={formatDateTime(document.uploadedAt)} />
          <Detail term="Last run" value={document.lastRunAt ? `${document.lastRunLabel} (${formatDateTime(document.lastRunAt)})` : document.lastRunLabel} />
          <Detail term="Size" value={formatFileSize(document.byteSize)} />
        </dl>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Uploader</h3>
        <dl className="space-y-2">
          <Detail term="Name" value={document.uploaderName} />
          {document.uploaderEmail ? <Detail term="Email" value={document.uploaderEmail} /> : null}
        </dl>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metadata</h3>
        <pre className="max-h-64 overflow-auto rounded-md bg-slate-100 p-3 text-xs text-slate-700">
          {JSON.stringify(document.metadata, null, 2)}
        </pre>
      </section>
    </div>
  );
}

function Detail({ term, value }: { readonly term: string; readonly value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{term}</dt>
      <dd className="max-w-[65%] truncate text-sm text-slate-700" title={value}>
        {value}
      </dd>
    </div>
  );
}
