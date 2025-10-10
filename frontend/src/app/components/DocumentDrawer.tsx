import { useMemo, useState } from "react";
import type { MouseEvent } from "react";

import { Button } from "../../ui";

type DocumentViewer = {
  readonly id: string;
  readonly initials: string;
  readonly color: string;
};

type DocumentEntry = {
  readonly id: string;
  readonly name: string;
  readonly updatedAt: string;
  readonly pinned?: boolean;
  readonly viewers: DocumentViewer[];
};

type HydratedDocument = DocumentEntry & { readonly pinned: boolean };

export interface DocumentDrawerProps {
  readonly workspaceId: string;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onSelectDocument: (documentId: string) => void;
  readonly onCreateDocument?: () => void;
}

export function DocumentDrawer({
  workspaceId,
  collapsed,
  onToggleCollapse,
  onSelectDocument,
  onCreateDocument,
}: DocumentDrawerProps) {
  const [query, setQuery] = useState("");
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);

  const documents = useMemo<DocumentEntry[]>(
    () => [
      {
        id: `${workspaceId}-1`,
        name: "Invoice batch – March",
        updatedAt: "2 minutes ago",
        viewers: [
          { id: "u1", initials: "AB", color: "bg-brand-500" },
          { id: "u2", initials: "CD", color: "bg-emerald-500" },
        ],
      },
      {
        id: `${workspaceId}-2`,
        name: "Vendor intake forms",
        updatedAt: "14 minutes ago",
        pinned: true,
        viewers: [{ id: "u3", initials: "EF", color: "bg-amber-500" }],
      },
      {
        id: `${workspaceId}-3`,
        name: "Quarterly summary template",
        updatedAt: "Yesterday",
        viewers: [],
      },
    ],
    [workspaceId],
  );

  const hydratedDocuments = useMemo<HydratedDocument[]>(
    () =>
      documents.map((doc) => ({
        ...doc,
        pinned: pinnedIds.includes(doc.id) || Boolean(doc.pinned),
      })),
    [documents, pinnedIds],
  );

  const filteredDocuments = useMemo<HydratedDocument[]>(() => {
    const search = query.trim().toLowerCase();
    if (!search) {
      return hydratedDocuments;
    }
    return hydratedDocuments.filter((doc) => doc.name.toLowerCase().includes(search));
  }, [hydratedDocuments, query]);

  const pinnedDocuments = useMemo(
    () => filteredDocuments.filter((doc) => doc.pinned),
    [filteredDocuments],
  );

  const recentDocuments = useMemo(
    () => filteredDocuments.filter((doc) => !doc.pinned),
    [filteredDocuments],
  );

  const showEmptyState = filteredDocuments.length === 0;

  function handlePinToggle(event: MouseEvent<HTMLButtonElement>, documentId: string, pinned: boolean) {
    event.stopPropagation();
    setPinnedIds((current) => {
      if (pinned) {
        return current.filter((id) => id !== documentId);
      }
      return current.includes(documentId) ? current : [...current, documentId];
    });
  }

  if (collapsed) {
    return (
      <aside className="flex h-full min-h-0 flex-col items-center gap-4 py-4">
        <button
          type="button"
          onClick={onCreateDocument}
          disabled={!onCreateDocument}
          className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-brand-300"
          title={onCreateDocument ? "Upload document" : "Upload coming soon"}
        >
          <span className="sr-only">Upload document</span>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 4a.75.75 0 01.75.75v4.5h4.5a.75.75 0 010 1.5h-4.5v4.5a.75.75 0 01-1.5 0v-4.5h-4.5a.75.75 0 010-1.5h4.5v-4.5A.75.75 0 0110 4z" />
          </svg>
        </button>

        <nav className="flex-1 overflow-y-auto">
          <ul className="flex flex-col items-center gap-2">
            {pinnedDocuments.map((document) => (
              <CollapsedDocumentButton
                key={document.id}
                document={document}
                onSelect={onSelectDocument}
              />
            ))}
            {pinnedDocuments.length > 0 && recentDocuments.length > 0 ? (
              <li className="my-1 h-px w-10 bg-slate-300/70" aria-hidden="true" />
            ) : null}
            {recentDocuments.map((document) => (
              <CollapsedDocumentButton
                key={document.id}
                document={document}
                onSelect={onSelectDocument}
              />
            ))}
            {showEmptyState ? (
              <li className="mt-2 text-center text-[10px] uppercase tracking-wide text-slate-400">
                No matches
              </li>
            ) : null}
          </ul>
        </nav>

        <CollapseButton collapsed={collapsed} onToggle={onToggleCollapse} />
      </aside>
    );
  }

  return (
    <aside className="flex h-full min-h-0 flex-col gap-4">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Documents</p>
            <h2 className="text-sm font-semibold text-slate-900">Switch between extractions</h2>
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            className="shrink-0"
            onClick={onCreateDocument}
            disabled={!onCreateDocument}
            title={onCreateDocument ? "Upload document" : "Upload coming soon"}
          >
            Upload
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search documents"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
              aria-label="Search documents"
            />
            <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M5 11a6 6 0 1112 0 6 6 0 01-12 0z" />
              </svg>
            </span>
          </div>

          <button
            type="button"
            onClick={() => setQuery("")}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-500 transition hover:bg-slate-50"
            aria-label="Clear search"
            disabled={query.length === 0}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {pinnedDocuments.length > 0 ? (
          <DocumentSection
            title="Pinned"
            documents={pinnedDocuments}
            onSelectDocument={onSelectDocument}
            onPinToggle={handlePinToggle}
          />
        ) : null}

        {pinnedDocuments.length > 0 && recentDocuments.length > 0 ? (
          <div className="border-t border-slate-200/70" />
        ) : null}

        <DocumentSection
          title="Recent"
          documents={recentDocuments}
          emptyMessage={showEmptyState ? "No documents match your search yet." : undefined}
          onSelectDocument={onSelectDocument}
          onPinToggle={handlePinToggle}
        />
      </div>

      <div className="flex items-center justify-between border-t border-transparent pt-2">
        <span className="text-xs text-slate-400">Collapse panel</span>
        <CollapseButton collapsed={collapsed} onToggle={onToggleCollapse} />
      </div>
    </aside>
  );
}

function DocumentSection({
  title,
  documents,
  emptyMessage,
  onSelectDocument,
  onPinToggle,
}: {
  title?: string;
  documents: HydratedDocument[];
  emptyMessage?: string;
  onSelectDocument: (documentId: string) => void;
  onPinToggle: (event: MouseEvent<HTMLButtonElement>, documentId: string, pinned: boolean) => void;
}) {
  if (documents.length === 0) {
    return emptyMessage ? (
      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-xs text-slate-500">
        {emptyMessage}
      </div>
    ) : null;
  }

  return (
    <section className="space-y-2">
      {title ? <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p> : null}
      <ul className="space-y-2 text-sm text-slate-600" aria-label={title ? `${title} documents` : "Documents"}>
        {documents.map((document) => (
          <DocumentListItem
            key={document.id}
            document={document}
            onSelectDocument={onSelectDocument}
            onPinToggle={onPinToggle}
          />
        ))}
      </ul>
    </section>
  );
}

function DocumentListItem({
  document,
  onSelectDocument,
  onPinToggle,
}: {
  document: HydratedDocument;
  onSelectDocument: (documentId: string) => void;
  onPinToggle: (event: MouseEvent<HTMLButtonElement>, documentId: string, pinned: boolean) => void;
}) {
  const { id, name, updatedAt, viewers, pinned } = document;

  return (
    <li>
      <div className="group flex items-center gap-3 rounded-lg border border-transparent px-3 py-3 transition hover:border-slate-200 hover:bg-slate-50 focus-within:border-slate-200 focus-within:bg-slate-50">
        <button
          type="button"
          onClick={() => onSelectDocument(id)}
          className="flex flex-1 flex-col text-left"
        >
          <span className="font-semibold text-slate-800 group-hover:text-brand-600 group-focus-within:text-brand-600">
            {name}
          </span>
          <span className="text-xs text-slate-500">Updated {updatedAt}</span>
        </button>
        <div className="flex items-center gap-2">
          {viewers.length > 0 ? (
            <ViewerStack viewers={viewers} />
          ) : (
            <span className="rounded-full border border-dashed border-slate-300 px-2 py-1 text-[10px] uppercase tracking-wide text-slate-400">
              Idle
            </span>
          )}
          <button
            type="button"
            onClick={(event) => onPinToggle(event, id, pinned)}
            className={`focus-ring inline-flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold transition opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 ${
              pinned
                ? "border-brand-200 bg-brand-50 text-brand-600"
                : "border-slate-200 bg-white text-slate-400 hover:border-slate-300 hover:text-slate-600"
            }`}
          >
            <span className="sr-only">{pinned ? "Unpin document" : "Pin document"}</span>
            {pinned ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M5.05 2.5a2.5 2.5 0 00-.858 4.853L9 8.618V13.5a.5.5 0 00.757.429l1.5-.9a.5.5 0 00.243-.429V8.618l4.808-1.265A2.5 2.5 0 0014.95 2.5H5.05z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v12m6-6H6" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </li>
  );
}

function ViewerStack({ viewers }: { viewers: DocumentViewer[] }) {
  return (
    <ul className="flex items-center -space-x-2">
      {viewers.map((viewer) => (
        <li
          key={viewer.id}
          className={`flex h-6 w-6 items-center justify-center rounded-full border-2 border-white text-[10px] font-semibold text-white ${viewer.color}`}
        >
          {viewer.initials}
        </li>
      ))}
    </ul>
  );
}

function CollapsedDocumentButton({
  document,
  onSelect,
}: {
  document: HydratedDocument;
  onSelect: (documentId: string) => void;
}) {
  const glyph = getDocumentGlyph(document.name);
  const pinnedStyle = document.pinned
    ? "border-brand-200 bg-brand-50 text-brand-700"
    : "border-transparent bg-slate-200 text-slate-700 hover:bg-slate-300";

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(document.id)}
        className={`focus-ring flex h-9 w-9 items-center justify-center rounded-full border-2 text-[10px] font-semibold transition ${pinnedStyle}`}
        title={`${document.name} • Updated ${document.updatedAt}`}
      >
        {glyph}
      </button>
    </li>
  );
}

function CollapseButton({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50"
    >
      <span className="sr-only">{collapsed ? "Expand documents panel" : "Collapse documents panel"}</span>
      {collapsed ? (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M7.47 4.47a.75.75 0 011.06 0l5.25 5.25a.75.75 0 010 1.06l-5.25 5.25a.75.75 0 01-1.06-1.06L11.69 10 7.47 5.78a.75.75 0 010-1.06z"
            clipRule="evenodd"
          />
        </svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M12.53 4.47a.75.75 0 010 1.06L8.31 10l4.22 4.22a.75.75 0 01-1.06 1.06L6.22 10.91a.75.75 0 010-1.06l5.25-5.25a.75.75 0 011.06 0z"
            clipRule="evenodd"
          />
        </svg>
      )}
    </button>
  );
}

function getDocumentGlyph(name: string) {
  const trimmed = name.trim();
  if (!trimmed) {
    return "D";
  }
  const words = trimmed.split(/\s+/);
  if (words.length === 1) {
    return words[0]!.slice(0, 2).toUpperCase();
  }
  return `${words[0]?.[0] ?? ""}${words[1]?.[0] ?? ""}`.toUpperCase();
}
