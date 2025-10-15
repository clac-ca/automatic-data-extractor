import { useMemo, useState } from "react";
import clsx from "clsx";

import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";

interface WorkspaceDocumentNavProps {
  readonly workspaceId: string;
  readonly selectedDocumentId?: string | null;
  readonly onSelectDocument: (documentId: string) => void;
  readonly onCreateDocument: () => void;
  readonly collapsed?: boolean;
}

export function WorkspaceDocumentNav({
  workspaceId,
  selectedDocumentId,
  onSelectDocument,
  onCreateDocument,
  collapsed = false,
}: WorkspaceDocumentNavProps) {
  const [search, setSearch] = useState("");
  const documentsQuery = useWorkspaceDocumentsQuery(workspaceId);
  const documents = useMemo(() => documentsQuery.data ?? [], [documentsQuery.data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      return documents;
    }
    return documents.filter((document) => document.name.toLowerCase().includes(term));
  }, [documents, search]);

  const pinned = useMemo(
    () =>
      filtered.filter((document) => {
        const metadata = (document.metadata ?? {}) as { pinned?: boolean };
        return metadata.pinned === true;
      }),
    [filtered],
  );

  const others = useMemo(
    () =>
      filtered
        .filter((document) => {
          const metadata = (document.metadata ?? {}) as { pinned?: boolean };
          return metadata.pinned !== true;
        })
        .sort(
          (a, b) =>
            new Date(b.updatedAt).getTime() -
            new Date(a.updatedAt).getTime(),
        ),
    [filtered],
  );

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-3 pt-3">
        <button
          type="button"
          onClick={onCreateDocument}
          className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          title="New document"
          aria-label="Create new document"
        >
          +
        </button>
        {renderCollapsedDocuments([...pinned, ...others], selectedDocumentId, onSelectDocument)}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onCreateDocument}
          className="focus-ring inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
        >
          <span className="text-base">+</span>
          New document
        </button>
      </div>

      <div className="relative">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search documents"
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        />
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-300">
          ⌘K
        </span>
      </div>

      {documentsQuery.isLoading ? (
        <p className="px-1 text-sm text-slate-500">Loading documents…</p>
      ) : documentsQuery.isError ? (
        <p className="px-1 text-sm text-red-500">Unable to load documents.</p>
      ) : filtered.length === 0 ? (
        <p className="px-1 text-sm text-slate-500">No documents match your search.</p>
      ) : (
        <div className="space-y-6 overflow-y-auto pb-4 pr-1">
          {pinned.length > 0 ? (
            <section>
              <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Pinned
              </h3>
              <ul className="mt-2 space-y-1">
                {pinned.map((document) => (
                  <li key={document.id}>
                    <DocumentNavItem
                      document={document}
                      selected={document.id === selectedDocumentId}
                      onSelect={onSelectDocument}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section>
            <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Documents
            </h3>
            <ul className="mt-2 space-y-1">
              {others.map((document) => (
                <li key={document.id}>
                  <DocumentNavItem
                    document={document}
                    selected={document.id === selectedDocumentId}
                    onSelect={onSelectDocument}
                  />
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}

function renderCollapsedDocuments(
  documents: WorkspaceDocument[],
  selectedDocumentId: string | null | undefined,
  onSelectDocument: (documentId: string) => void,
) {
  return documents.slice(0, 6).map((document) => {
    const glyph = getDocumentGlyph(document.name);
    const isSelected = document.id === selectedDocumentId;
    return (
      <button
        key={document.id}
        type="button"
        onClick={() => onSelectDocument(document.id)}
        className={clsx(
          "focus-ring flex h-10 w-10 items-center justify-center rounded-full border text-xs font-semibold transition",
          isSelected
            ? "border-brand-200 bg-brand-50 text-brand-700"
            : "border-slate-200 bg-white text-slate-500 hover:border-brand-200 hover:text-brand-700",
        )}
        title={document.name}
        aria-pressed={isSelected}
      >
        {glyph}
      </button>
    );
  });
}

interface WorkspaceDocument {
  readonly id: string;
  readonly name: string;
  readonly updatedAt: string;
  readonly metadata?: Record<string, unknown>;
}

function DocumentNavItem({
  document,
  selected,
  onSelect,
}: {
  readonly document: WorkspaceDocument;
  readonly selected: boolean;
  readonly onSelect: (documentId: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(document.id)}
      aria-pressed={selected}
      className={clsx(
        "group flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
        selected
          ? "bg-brand-100 text-brand-800 shadow-sm"
          : "text-slate-600 hover:bg-slate-100",
      )}
    >
      <span className="flex min-w-0 flex-col">
        <span className="truncate font-semibold">{document.name}</span>
        <span className="truncate text-xs text-slate-400">
          Updated {formatUpdatedAt(document.updatedAt)}
        </span>
      </span>
      <span className="text-slate-300 group-hover:text-brand-500">›</span>
    </button>
  );
}

function getDocumentGlyph(name: string) {
  const [first = "?", second = ""] = name
    .split(" ")
    .map((segment) => segment.trim())
    .filter(Boolean);
  const letters = `${first.charAt(0)}${second.charAt(0)}`.toUpperCase();
  return letters || name.charAt(0).toUpperCase() || "?";
}

function formatUpdatedAt(timestamp: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(timestamp));
  } catch (error) {
    return timestamp;
  }
}
