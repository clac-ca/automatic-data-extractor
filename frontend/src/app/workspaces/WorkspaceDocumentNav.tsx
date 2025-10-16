import { useEffect, useMemo, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import { PinIcon as PinStatusIcon, ArchiveIcon as ArchiveStatusIcon } from "./icons";

export type DocumentViewMode = "all" | "recent" | "pinned" | "archived";

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

  const orderedDocuments = useMemo(() => {
    const pinnedDocs: WorkspaceDocument[] = [];
    const otherDocs: WorkspaceDocument[] = [];
    documents.forEach((document) => {
      const metadata = (document.metadata ?? {}) as DocumentMetadata;
      if (metadata.pinned === true) {
        pinnedDocs.push(document);
      } else {
        otherDocs.push(document);
      }
    });

    pinnedDocs.sort(
      (a, b) =>
        new Date(b.updatedAt).getTime() -
        new Date(a.updatedAt).getTime(),
    );
    otherDocs.sort(
      (a, b) =>
        new Date(b.updatedAt).getTime() -
        new Date(a.updatedAt).getTime(),
    );

    return { pinnedDocs, otherDocs };
  }, [documents]);

  const visibleDocuments = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      return {
        pinned: orderedDocuments.pinnedDocs,
        others: orderedDocuments.otherDocs,
      };
    }
    const filteredPinned = orderedDocuments.pinnedDocs.filter((document) =>
      document.name.toLowerCase().includes(term),
    );
    const filteredOthers = orderedDocuments.otherDocs.filter((document) =>
      document.name.toLowerCase().includes(term),
    );
    return { pinned: filteredPinned, others: filteredOthers };
  }, [orderedDocuments.otherDocs, orderedDocuments.pinnedDocs, search]);

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-3 pt-3">
        <button
          type="button"
          onClick={onCreateDocument}
          className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-base font-semibold text-white shadow-sm transition hover:bg-brand-700"
          title="New document"
          aria-label="Create new document"
        >
          +
        </button>
        {renderCollapsedDocuments(
          [...visibleDocuments.pinned, ...visibleDocuments.others],
          selectedDocumentId,
          onSelectDocument,
        )}
      </div>
    );
  }

  let listContent: ReactNode;
  if (documentsQuery.isLoading) {
    listContent = <p className="px-1 text-sm text-slate-500">Loading documents…</p>;
  } else if (documentsQuery.isError) {
    listContent = <p className="px-1 text-sm text-red-500">Unable to load documents.</p>;
  } else if (
    visibleDocuments.pinned.length === 0 &&
    visibleDocuments.others.length === 0
  ) {
    const emptyMessage =
      search.trim().length > 0
        ? "No documents match your search."
        : "No documents in this workspace yet.";
    listContent = (
      <div className="rounded-xl border border-dashed border-slate-200 px-3 py-4 text-sm text-slate-500">
        {emptyMessage}
      </div>
    );
  } else {
    listContent = (
      <div className="space-y-6">
        {visibleDocuments.pinned.length > 0 ? (
          <section>
            <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Pinned</h3>
            <ul className="mt-2 space-y-1">
              {visibleDocuments.pinned.map((document) => (
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
          <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Documents</h3>
          <ul className="mt-2 space-y-1">
            {visibleDocuments.others.map((document) => (
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
    );
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <button
        type="button"
        onClick={onCreateDocument}
        className="focus-ring inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
      >
        <span className="text-base">+</span>
        New document
      </button>

      <div className="relative">
        <label htmlFor="document-quick-search" className="sr-only">
          Search documents
        </label>
        <input
          id="document-quick-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search documents"
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 pl-10 text-sm text-slate-700 shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        />
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-300">
          <SearchIcon />
        </span>
        <span className="pointer-events-none absolute inset-y-0 right-3 hidden items-center gap-1 text-xs text-slate-300 sm:flex">
          <kbd className="rounded border border-slate-200 px-1 py-0.5 font-sans text-[11px]">⌘</kbd>
          <kbd className="rounded border border-slate-200 px-1 py-0.5 font-sans text-[11px]">K</kbd>
        </span>
      </div>

      <div className="flex-1 overflow-y-auto pb-4 pr-1">{listContent}</div>
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
    const metadata = (document.metadata ?? {}) as DocumentMetadata;
    const isPinned = metadata.pinned === true;
    const isArchived = metadata.archived === true;
    return (
      <button
        key={document.id}
        type="button"
        onClick={() => onSelectDocument(document.id)}
        className={clsx(
          "focus-ring flex h-10 w-10 items-center justify-center rounded-full border text-xs font-semibold transition",
          isSelected
            ? "border-brand-200 bg-brand-50 text-brand-700"
            : isPinned
              ? "border-brand-200 bg-brand-50 text-brand-600 hover:border-brand-300"
              : isArchived
                ? "border-slate-200 bg-slate-100 text-slate-400 hover:border-slate-300"
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

interface DocumentMetadata {
  readonly pinned?: boolean;
  readonly archived?: boolean;
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
  const glyph = getDocumentGlyph(document.name);
  const metadata = (document.metadata ?? {}) as DocumentMetadata;
  const isPinned = metadata.pinned === true;
  const isArchived = metadata.archived === true;
  const glyphClass = selected
    ? "border-white/30 bg-white/10 text-white"
    : isPinned
      ? "border-brand-200 bg-brand-50 text-brand-600"
      : isArchived
        ? "border-slate-200 bg-slate-100 text-slate-400"
        : "border-slate-200 bg-slate-50 text-slate-500";
  const pinnedIconTone = selected ? "text-white/80" : "text-brand-500";
  const archivedIconTone = selected ? "text-white/70" : "text-slate-400";
  return (
    <button
      type="button"
      onClick={() => onSelect(document.id)}
      aria-pressed={selected}
      aria-current={selected ? "true" : undefined}
      className={clsx(
        "group flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
        selected
          ? "bg-gradient-to-r from-brand-600 via-brand-600 to-brand-500 text-white shadow-lg"
          : "bg-white/90 text-slate-600 shadow-[0_1px_2px_rgba(15,23,42,0.08)] hover:bg-white",
      )}
    >
      <span
        className={clsx(
          "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border text-sm font-semibold transition",
          glyphClass,
        )}
      >
        {glyph}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-1">
          <span className="truncate font-semibold">{document.name}</span>
          {isPinned ? (
            <PinStatusIcon className={clsx("h-3.5 w-3.5", pinnedIconTone)} aria-hidden="true" />
          ) : null}
          {isArchived ? (
            <ArchiveStatusIcon className={clsx("h-3.5 w-3.5", archivedIconTone)} aria-hidden="true" />
          ) : null}
        </span>
        <span className={clsx("truncate text-xs", selected ? "text-white/80" : "text-slate-400")}>
          Updated {formatUpdatedAt(document.updatedAt)}
        </span>
      </span>
      <span
        className={clsx(
          "text-base transition-transform",
          selected ? "translate-x-1 text-white" : "text-slate-300 group-hover:translate-x-1 group-hover:text-brand-500",
        )}
        aria-hidden="true"
      >
        ›
      </span>
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
  } catch {
    return timestamp;
  }
}

type WorkspaceQuickSwitcherSize = "regular" | "compact";
type WorkspaceQuickSwitcherTone = "solid" | "ghost";

interface WorkspaceQuickSwitcherProps {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: readonly WorkspaceProfile[];
  readonly onSelectWorkspace: (workspaceId: string) => void;
  readonly onCreateWorkspace?: () => void;
  readonly onManageWorkspace?: () => void;
  readonly collapsed?: boolean;
  readonly size?: WorkspaceQuickSwitcherSize;
  readonly tone?: WorkspaceQuickSwitcherTone;
  readonly className?: string;
  readonly showSlug?: boolean;
  readonly glyphOverride?: string;
  readonly title?: string;
  readonly subtitle?: string;
  readonly variant?: "default" | "brand";
}

export function WorkspaceQuickSwitcher({
  workspace,
  workspaces,
  onSelectWorkspace,
  onCreateWorkspace,
  onManageWorkspace,
  collapsed = false,
  size = "regular",
  tone = "solid",
  className,
  showSlug = true,
  glyphOverride,
  title,
  subtitle,
  variant = "default",
}: WorkspaceQuickSwitcherProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current) {
        return;
      }
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const otherWorkspaces = useMemo(
    () => workspaces.filter((candidate) => candidate.id !== workspace.id),
    [workspaces, workspace.id],
  );

  const isCompact = size === "compact";
  const isGhost = tone === "ghost";
  const isBrand = variant === "brand";

  return (
    <div
      ref={containerRef}
      className={clsx(
        "relative",
        collapsed ? "flex flex-col items-center" : "w-auto",
        className,
      )}
      onBlur={(event) => {
        if (!containerRef.current) {
          return;
        }
        const nextTarget = event.relatedTarget as Node | null;
        if (!nextTarget || !containerRef.current.contains(nextTarget)) {
          setOpen(false);
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={clsx(
          "focus-ring inline-flex items-center gap-3 text-sm font-semibold transition motion-safe:duration-150",
          collapsed
            ? "h-11 w-11 justify-center rounded-full border border-slate-300 bg-white text-slate-700 shadow-sm hover:border-slate-400 hover:text-slate-900"
            : clsx(
                "rounded-xl",
                isBrand
                  ? "min-w-0 border border-transparent bg-white px-3 py-2 text-left shadow-sm hover:bg-slate-100"
                  : [
                      isCompact ? "h-10 px-2.5 py-1.5" : "px-3 py-3 shadow-sm",
                      isGhost
                        ? "border border-transparent bg-transparent text-slate-600 hover:bg-white/80 hover:text-slate-900"
                        : "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900",
                    ],
              ),
        )}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={
          collapsed
            ? "Switch workspace"
            : variant === "brand"
              ? `Workspace selector. Current workspace: ${workspace.name}`
              : `Workspace: ${workspace.name}`
        }
      >
        <span
          className={clsx(
            "inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border text-sm",
            collapsed
              ? "border-transparent bg-brand-100 text-brand-700"
              : clsx(
                  isBrand ? "border-transparent bg-brand-600 text-white" : "border-brand-100 bg-brand-50 text-brand-700",
                  isGhost && !isBrand && "border-transparent bg-white/60 text-brand-600",
                ),
          )}
        >
          {glyphOverride ?? getWorkspaceGlyph(workspace.name)}
        </span>
        {collapsed ? null : (
          <span className="flex min-w-0 flex-1 flex-col text-left">
            <span className="truncate text-sm font-semibold text-slate-900">
              {isBrand ? title ?? "Automatic Data Extractor" : workspace.name}
            </span>
            <span className="truncate text-xs text-slate-400">
              {isBrand
                ? subtitle ?? workspace.name
                : showSlug
                  ? workspace.slug
                    ? `/${workspace.slug}`
                    : "Active workspace"
                  : undefined}
            </span>
          </span>
        )}
        <span
          className={clsx(
            "text-slate-400 transition-transform",
            open ? "rotate-180" : "",
          )}
        >
          ▾
        </span>
      </button>

      {open ? (
        <div
          role="menu"
          aria-label="Workspaces"
          className={clsx(
            "absolute z-10 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-3 text-sm shadow-xl",
            collapsed ? "left-1/2 -translate-x-1/2" : "left-0",
          )}
        >
          <div className="space-y-1">
            {onManageWorkspace ? (
              <WorkspaceMenuButton
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onManageWorkspace();
                }}
                icon="⚙️"
                label="Workspace settings"
                description="Members, permissions, integrations"
              />
            ) : null}
            {onCreateWorkspace ? (
              <WorkspaceMenuButton
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onCreateWorkspace();
                }}
                icon="＋"
                label="Create workspace"
                description="Start a fresh workspace"
              />
            ) : null}
          </div>
          {otherWorkspaces.length > 0 ? (
            <div className="mt-3 space-y-1">
              <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Switch workspace
              </p>
              <ul className="mt-2 space-y-1">
                {otherWorkspaces.map((candidate) => (
                  <li key={candidate.id}>
                    <WorkspaceMenuButton
                      role="menuitem"
                      onClick={() => {
                        setOpen(false);
                        onSelectWorkspace(candidate.id);
                      }}
                      icon={getWorkspaceGlyph(candidate.name)}
                      label={candidate.name}
                      description={candidate.slug ? `/${candidate.slug}` : undefined}
                    />
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-3 px-2 text-xs text-slate-400">You&apos;re already in your only workspace.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

interface WorkspaceMenuButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly icon: string;
  readonly label: string;
  readonly description?: string;
}

function WorkspaceMenuButton({ icon, label, description, className, ...props }: WorkspaceMenuButtonProps) {
  return (
    <button
      type="button"
      className={clsx(
        "flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    >
      <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600">
        {icon}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="truncate font-semibold text-slate-800">{label}</span>
        {description ? <span className="truncate text-xs text-slate-400">{description}</span> : null}
      </span>
    </button>
  );
}

function getWorkspaceGlyph(name: string) {
  return getDocumentGlyph(name);
}

function SearchIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M8.5 3a5.5 5.5 0 013.934 9.35l3.108 3.107a1 1 0 01-1.414 1.415l-3.108-3.108A5.5 5.5 0 118.5 3zm0 2a3.5 3.5 0 100 7 3.5 3.5 0 000-7z"
        clipRule="evenodd"
      />
    </svg>
  );
}
