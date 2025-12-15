import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode } from "react";

import clsx from "clsx";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { createScopedStorage } from "@shared/storage";

import type { WorkbenchFileNode } from "../types";

type ExplorerTheme = "light" | "dark";
type CreateTarget = { readonly parentId: string; readonly kind: "file" | "folder" } | null;

interface ExplorerThemeTokens {
  readonly surface: string;
  readonly border: string;
  readonly heading: string;
  readonly label: string;
  readonly textPrimary: string;
  readonly textMuted: string;
  readonly rowHover: string;
  readonly folderActiveBg: string;
  readonly selectionBg: string;
  readonly selectionText: string;
  readonly badgeActive: string;
  readonly badgeOpen: string;
  readonly folderIcon: string;
  readonly folderIconActive: string;
  readonly chevronIdle: string;
  readonly chevronActive: string;
}

const EXPLORER_THEME_TOKENS: Record<ExplorerTheme, ExplorerThemeTokens> = {
  dark: {
    surface: "#1e1e1e",
    border: "#252526",
    heading: "#cccccc",
    label: "#999999",
    textPrimary: "#f3f3f3",
    textMuted: "#c5c5c5",
    rowHover: "#2a2d2e",
    folderActiveBg: "transparent",
    selectionBg: "#2f3136",
    selectionText: "#f8f8f8",
    badgeActive: "#4fc1ff",
    badgeOpen: "#858585",
    folderIcon: "#c8ae7d",
    folderIconActive: "#e0c08e",
    chevronIdle: "#7a7a7a",
    chevronActive: "#d4d4d4",
  },
  light: {
    surface: "#f3f3f3",
    border: "#d4d4d4",
    heading: "#616161",
    label: "#8a8a8a",
    textPrimary: "#1e1e1e",
    textMuted: "#555555",
    rowHover: "#e8e8e8",
    folderActiveBg: "transparent",
    selectionBg: "#dcdcdc",
    selectionText: "#0f172a",
    badgeActive: "#0e639c",
    badgeOpen: "#6b6b6b",
    folderIcon: "#c0933a",
    folderIconActive: "#a67c32",
    chevronIdle: "#7a7a7a",
    chevronActive: "#3c3c3c",
  },
};

const FOCUS_RING_CLASS: Record<ExplorerTheme, string> = {
  dark: "focus-visible:ring-2 focus-visible:ring-[#007acc] focus-visible:ring-offset-2 focus-visible:ring-offset-[#252526]",
  light: "focus-visible:ring-2 focus-visible:ring-[#007acc] focus-visible:ring-offset-2 focus-visible:ring-offset-white",
};

function collectFolderIds(node: WorkbenchFileNode): Set<string> {
  const ids = new Set<string>();
  const visit = (current: WorkbenchFileNode) => {
    if (current.kind !== "folder") {
      return;
    }
    ids.add(current.id);
    current.children?.forEach(visit);
  };
  visit(node);
  return ids;
}

function sanitizeExpandedSet(
  candidate: Iterable<string>,
  availableFolderIds: ReadonlySet<string>,
  rootId: string,
): Set<string> {
  const next = new Set<string>();
  for (const id of candidate) {
    if (availableFolderIds.has(id)) {
      next.add(id);
    }
  }
  next.add(rootId);
  return next;
}

function areSetsEqual(a: ReadonlySet<string>, b: ReadonlySet<string>) {
  if (a.size !== b.size) return false;
  for (const value of a) {
    if (!b.has(value)) {
      return false;
    }
  }
  return true;
}

interface ExplorerProps {
  readonly width: number;
  readonly tree: WorkbenchFileNode;
  readonly activeFileId?: string;
  readonly openFileIds?: readonly string[];
  readonly onSelectFile: (fileId: string) => void;
  readonly theme: ExplorerTheme;
  readonly canCreateFile?: boolean;
  readonly canCreateFolder?: boolean;
  readonly isCreatingEntry?: boolean;
  readonly onCreateFile?: (folderPath: string, fileName: string) => Promise<void>;
  readonly onCreateFolder?: (folderPath: string, folderName: string) => Promise<void>;
  readonly canDeleteFile?: boolean;
  readonly deletingFilePath?: string | null;
  readonly canDeleteFolder?: boolean;
  readonly deletingFolderPath?: string | null;
  readonly onDeleteFile?: (filePath: string) => Promise<void>;
  readonly onDeleteFolder?: (folderPath: string) => Promise<void>;
  readonly expandedStorageKey?: string;
  readonly onHide: () => void;
}

export function Explorer({
  width,
  tree,
  activeFileId = "",
  openFileIds = [],
  onSelectFile,
  theme,
  canCreateFile = false,
  canCreateFolder = false,
  isCreatingEntry = false,
  onCreateFile,
  onCreateFolder,
  canDeleteFile = false,
  deletingFilePath = null,
  canDeleteFolder = false,
  deletingFolderPath = null,
  onDeleteFile,
  onDeleteFolder,
  expandedStorageKey,
  onHide,
}: ExplorerProps) {
  const expansionStorage = useMemo(
    () => (expandedStorageKey ? createScopedStorage(expandedStorageKey) : null),
    [expandedStorageKey],
  );
  const availableFolderIds = useMemo(() => collectFolderIds(tree), [tree]);
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const stored = expansionStorage?.get<string[]>() ?? null;
    const candidate = stored ? new Set(stored) : new Set<string>([tree.id]);
    return sanitizeExpandedSet(candidate, availableFolderIds, tree.id);
  });
  const [contextMenu, setContextMenu] = useState<{
    readonly node: WorkbenchFileNode;
    readonly position: { readonly x: number; readonly y: number };
  } | null>(null);
  const [editing, setEditing] = useState<CreateTarget>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    setEditing(null);
    setCreateError(null);
  }, [tree.id]);

  useEffect(() => {
    setExpanded((prev) => {
      const next = sanitizeExpandedSet(prev, availableFolderIds, tree.id);
      return areSetsEqual(prev, next) ? prev : next;
    });
  }, [availableFolderIds, tree.id]);

  useEffect(() => {
    if (!expansionStorage) {
      return;
    }
    const stored = expansionStorage.get<string[]>();
    if (!stored) {
      return;
    }
    const next = sanitizeExpandedSet(new Set(stored), availableFolderIds, tree.id);
    setExpanded((prev) => (areSetsEqual(prev, next) ? prev : next));
  }, [expansionStorage, availableFolderIds, tree.id]);

  useEffect(() => {
    if (!expansionStorage) {
      return;
    }
    const payload = Array.from(expanded).filter((id) => id !== tree.id && availableFolderIds.has(id));
    expansionStorage.set(payload);
  }, [expanded, expansionStorage, availableFolderIds, tree.id]);

  const toggleFolder = useCallback(
    (nodeId: string) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(nodeId)) {
          next.delete(nodeId);
        } else {
          next.add(nodeId);
        }
        next.add(tree.id);
        return next;
      });
    },
    [tree.id],
  );

  const setFolderExpanded = useCallback(
    (nodeId: string, nextExpanded: boolean) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (nextExpanded) {
          next.add(nodeId);
        } else if (nodeId !== tree.id) {
          next.delete(nodeId);
        }
        next.add(tree.id);
        return next;
      });
    },
    [tree.id],
  );

  const collapseAll = useCallback(() => {
    setExpanded(new Set([tree.id]));
  }, [tree.id]);

  const startCreateEntry = useCallback(
    (parentId: string, kind: "file" | "folder") => {
      setCreateError(null);
      setExpanded((prev) => {
        const next = new Set(prev);
        next.add(tree.id);
        next.add(parentId);
        return next;
      });
      setEditing({ parentId, kind });
    },
    [tree.id],
  );

  const handleSubmitCreate = useCallback(
    async (parentId: string, name: string, kind: "file" | "folder") => {
      const trimmed = name.trim();
      if (!trimmed) {
        setCreateError("Name cannot be empty.");
        return;
      }
      const handler = kind === "folder" ? onCreateFolder : onCreateFile;
      if (!handler) {
        return;
      }
      try {
        setCreateError(null);
        await handler(parentId === tree.id ? "" : parentId, trimmed);
        setEditing(null);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to create entry.";
        setCreateError(message);
      }
    },
    [onCreateFile, onCreateFolder, tree.id],
  );

  const handleCancelCreate = useCallback(() => {
    setEditing(null);
    setCreateError(null);
  }, []);

  const handleNodeContextMenu = useCallback((event: MouseEvent, node: WorkbenchFileNode) => {
    event.preventDefault();
    setContextMenu({ node, position: { x: event.clientX, y: event.clientY } });
  }, []);

  const handleCopyPath = useCallback(async (path: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(path);
        return;
      } catch {
        // fall through to manual copy
      }
    }
    if (typeof document === "undefined") {
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = path;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }, []);

  const handleDeleteFile = useCallback(
    (path: string) => {
      if (!onDeleteFile) {
        return;
      }
      void onDeleteFile(path);
      setContextMenu(null);
    },
    [onDeleteFile],
  );

  const handleDeleteFolder = useCallback(
    (path: string) => {
      if (!onDeleteFolder) {
        return;
      }
      void onDeleteFolder(path);
      setContextMenu(null);
    },
    [onDeleteFolder],
  );

  const explorerMenuItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const { node } = contextMenu;
    const shortcuts = {
      open: "Enter",
      newFile: "Ctrl+N",
      newFolder: "Ctrl+Shift+N",
      copyPath: "Ctrl+K Ctrl+C",
      collapseAll: "Ctrl+K Ctrl+0",
      delete: "Delete",
    };

    if (node.kind === "file") {
      return [
        { id: "open-file", label: "Open", icon: <MenuIconOpenFile />, shortcut: shortcuts.open, onSelect: () => onSelectFile(node.id) },
        {
          id: "copy-path",
          label: "Copy Path",
          dividerAbove: true,
          icon: <MenuIconCopyPath />,
          shortcut: shortcuts.copyPath,
          onSelect: () => {
            void handleCopyPath(node.id);
          },
        },
        {
          id: "delete-file",
          label: "Delete",
          icon: <MenuIconDelete />,
          shortcut: shortcuts.delete,
          disabled: !canDeleteFile || !onDeleteFile,
          onSelect: () => handleDeleteFile(node.id),
        },
      ];
    }

    const isExpanded = expanded.has(node.id);
    return [
      {
        id: "new-file",
        label: "New File…",
        icon: <MenuIconNewFile />,
        shortcut: shortcuts.newFile,
        disabled: !canCreateFile || !onCreateFile,
        onSelect: () => {
          if (!canCreateFile || !onCreateFile) {
            return;
          }
          startCreateEntry(node.id, "file");
          setContextMenu(null);
        },
      },
      {
        id: "new-folder",
        label: "New Folder…",
        icon: <MenuIconNewFolder />,
        shortcut: shortcuts.newFolder,
        disabled: !canCreateFolder || !onCreateFolder,
        onSelect: () => {
          if (!canCreateFolder || !onCreateFolder) {
            return;
          }
          startCreateEntry(node.id, "folder");
          setContextMenu(null);
        },
      },
      {
        id: "toggle-folder",
        label: isExpanded ? "Collapse Folder" : "Expand Folder",
        icon: isExpanded ? <MenuIconCollapse /> : <MenuIconExpand />,
        onSelect: () => setFolderExpanded(node.id, !isExpanded),
      },
      {
        id: "collapse-all",
        label: "Collapse All",
        icon: <MenuIconCollapseAll />,
        shortcut: shortcuts.collapseAll,
        dividerAbove: true,
        onSelect: () => collapseAll(),
      },
      {
        id: "copy-path",
        label: "Copy Path",
        dividerAbove: true,
        icon: <MenuIconCopyPath />,
        shortcut: shortcuts.copyPath,
        onSelect: () => {
          void handleCopyPath(node.id);
        },
      },
      {
        id: "delete-folder",
        label: "Delete Folder",
        icon: <MenuIconDelete />,
        shortcut: shortcuts.delete,
        disabled: !canDeleteFolder || !onDeleteFolder,
        onSelect: () => handleDeleteFolder(node.id),
      },
    ];
  }, [
    contextMenu,
    onSelectFile,
    handleCopyPath,
    canDeleteFile,
    onDeleteFile,
    expanded,
    setFolderExpanded,
    collapseAll,
    canCreateFile,
    canCreateFolder,
    onCreateFile,
    onCreateFolder,
    startCreateEntry,
    canDeleteFolder,
    onDeleteFolder,
    handleDeleteFolder,
    handleDeleteFile,
  ]);

  const tokens = EXPLORER_THEME_TOKENS[theme];
  const focusRingClass = FOCUS_RING_CLASS[theme];
  const rootChildren = useMemo(() => tree.children ?? [], [tree]);
  const menuAppearance = theme === "dark" ? "dark" : "light";

  return (
    <>
      <aside
        className="flex h-full min-h-0 flex-col border-r text-[13px]"
        style={{
          width,
          backgroundColor: tokens.surface,
          borderColor: tokens.border,
          color: tokens.textPrimary,
        }}
        aria-label="Config files explorer"
      >
        <div
          className="flex items-center justify-between border-b px-3 py-2"
          style={{ borderColor: tokens.border, backgroundColor: theme === "dark" ? "#181818" : "#ececec" }}
        >
          <div className="text-[11px] font-semibold uppercase tracking-[0.3em]" style={{ color: tokens.heading }}>
            Explorer
          </div>
          <button
            type="button"
            onClick={onHide}
            aria-label="Hide explorer"
            className={clsx(
              "flex h-7 w-7 items-center justify-center rounded-md transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#007acc]",
              theme === "dark"
                ? "text-slate-300 hover:bg-white/10 hover:text-white"
                : "text-slate-600 hover:bg-black/10 hover:text-slate-900",
            )}
          >
            <HideSidebarIcon />
          </button>
        </div>
        <nav className="flex-1 overflow-auto px-2 py-2" aria-label="Workspace files tree">
          <ul className="space-y-0.5">
            {rootChildren.map((node) => (
              <ExplorerNode
                key={node.id}
                node={node}
                depth={0}
                expanded={expanded}
                activeFileId={activeFileId}
                openFileIds={openFileIds}
                onToggleFolder={toggleFolder}
                onSelectFile={onSelectFile}
                tokens={tokens}
                theme={theme}
                focusRingClass={focusRingClass}
                onContextMenu={handleNodeContextMenu}
                editing={editing}
                onSubmitCreateEntry={handleSubmitCreate}
                onCancelCreateEntry={handleCancelCreate}
                createError={createError}
                isCreatingEntry={isCreatingEntry}
                deletingFilePath={deletingFilePath}
                deletingFolderPath={deletingFolderPath}
                onClearCreateError={() => setCreateError(null)}
              />
            ))}
            {editing?.parentId === tree.id ? (
              <li className="pl-2">
                <CreateEntryRow
                  appearance={theme}
                  icon={editing.kind === "folder" ? <MenuIconNewFolder /> : undefined}
                  placeholder={editing.kind === "folder" ? "new_folder" : "new_file.py"}
                  onSubmit={(name) => handleSubmitCreate(tree.id, name, editing.kind)}
                  onCancel={handleCancelCreate}
                  onChange={() => setCreateError(null)}
                  isSubmitting={isCreatingEntry}
                  error={createError}
                />
              </li>
            ) : null}
          </ul>
        </nav>
      </aside>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu ? contextMenu.position : null}
        onClose={() => setContextMenu(null)}
        items={explorerMenuItems}
        appearance={menuAppearance}
      />
    </>
  );
}

interface ExplorerNodeProps {
  readonly node: WorkbenchFileNode;
  readonly depth: number;
  readonly expanded: ReadonlySet<string>;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onToggleFolder: (nodeId: string) => void;
  readonly onSelectFile: (fileId: string) => void;
  readonly tokens: ExplorerThemeTokens;
  readonly theme: ExplorerTheme;
  readonly focusRingClass: string;
  readonly onContextMenu: (event: MouseEvent, node: WorkbenchFileNode) => void;
  readonly editing: CreateTarget;
  readonly onSubmitCreateEntry: (folderId: string, name: string, kind: "file" | "folder") => Promise<void> | void;
  readonly onCancelCreateEntry: () => void;
  readonly createError: string | null;
  readonly isCreatingEntry: boolean;
  readonly deletingFilePath: string | null;
  readonly deletingFolderPath: string | null;
  readonly onClearCreateError: () => void;
}

function ExplorerNode({
  node,
  depth,
  expanded,
  activeFileId,
  openFileIds,
  onToggleFolder,
  onSelectFile,
  tokens,
  theme,
  focusRingClass,
  onContextMenu,
  editing,
  onSubmitCreateEntry,
  onCancelCreateEntry,
  createError,
  isCreatingEntry,
  deletingFilePath,
  deletingFolderPath,
  onClearCreateError,
}: ExplorerNodeProps) {
  const paddingLeft = 8 + depth * 16;
  const baseStyle: CSSProperties & { ["--tree-hover-bg"]?: string } = {
    paddingLeft,
    ["--tree-hover-bg"]: tokens.rowHover,
  };

  if (node.kind === "folder") {
    const isOpen = expanded.has(node.id);
    const isDeleting = deletingFolderPath === node.id;
    const isEditingHere = editing?.parentId === node.id;
    const folderStyle: CSSProperties = {
      ...baseStyle,
      color: isOpen ? tokens.textPrimary : tokens.textMuted,
    };
    if (isOpen && tokens.folderActiveBg !== "transparent") {
      folderStyle.backgroundColor = tokens.folderActiveBg;
    }

    return (
      <li className="relative">
        <button
          type="button"
          onClick={() => onToggleFolder(node.id)}
          onContextMenu={(event) => onContextMenu(event, node)}
          className={clsx(
            "group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-medium transition hover:bg-[var(--tree-hover-bg)]",
            focusRingClass,
            isDeleting && "opacity-60",
          )}
          style={folderStyle}
          aria-expanded={isOpen}
          disabled={isDeleting}
        >
          <ChevronIcon open={isOpen} tokens={tokens} />
          <FolderIcon open={isOpen} tokens={tokens} />
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen ? (
          <ul className="mt-0.5 space-y-0.5">
            {node.children?.map((child) => (
              <ExplorerNode
                key={child.id}
                node={child}
                depth={depth + 1}
                expanded={expanded}
                activeFileId={activeFileId}
                openFileIds={openFileIds}
                onToggleFolder={onToggleFolder}
                onSelectFile={onSelectFile}
                tokens={tokens}
                theme={theme}
                focusRingClass={focusRingClass}
                onContextMenu={onContextMenu}
                editing={editing}
                onSubmitCreateEntry={onSubmitCreateEntry}
                onCancelCreateEntry={onCancelCreateEntry}
                createError={createError}
                isCreatingEntry={isCreatingEntry}
                deletingFilePath={deletingFilePath}
                deletingFolderPath={deletingFolderPath}
                onClearCreateError={onClearCreateError}
              />
            ))}
            {isEditingHere ? (
              <li className="pl-2">
                <CreateEntryRow
                  appearance={theme}
                  icon={editing?.kind === "folder" ? <MenuIconNewFolder /> : undefined}
                  placeholder={editing?.kind === "folder" ? "new_folder" : "new_file.py"}
                  onSubmit={(name) => {
                    if (!editing) return;
                    onSubmitCreateEntry(node.id, name, editing.kind);
                  }}
                  onCancel={onCancelCreateEntry}
                  onChange={onClearCreateError}
                  isSubmitting={isCreatingEntry}
                  error={createError}
                />
              </li>
            ) : null}
          </ul>
        ) : null}
      </li>
    );
  }

  const isActive = activeFileId === node.id;
  const isOpen = openFileIds.includes(node.id);
  const isDeleting = deletingFilePath === node.id;
  const fileAccent = getFileAccent(node.name, node.language);
  const fileStyle: CSSProperties = { ...baseStyle, color: tokens.textPrimary };
  if (isActive) {
    fileStyle.backgroundColor = tokens.selectionBg;
    fileStyle.color = tokens.selectionText;
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelectFile(node.id)}
        onContextMenu={(event) => onContextMenu(event, node)}
        className={clsx(
          "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition hover:bg-[var(--tree-hover-bg)]",
          focusRingClass,
          isActive && "shadow-inner shadow-[#00000033]",
          isDeleting && "opacity-60",
        )}
        style={fileStyle}
        disabled={isDeleting}
      >
        <span className="inline-flex w-4 justify-center">
          <FileIcon className={clsx(fileAccent, isOpen && !isActive && "opacity-90", !isOpen && !isActive && "opacity-75")} />
        </span>
        <span className={clsx("flex-1 truncate", isActive && "font-semibold")}>{node.name}</span>
        {isOpen && !isActive ? <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: tokens.badgeOpen }} /> : null}
      </button>
    </li>
  );
}

const FILE_ICON_COLORS: Record<string, string> = {
  json: "text-[#f1d06b]",
  py: "text-[#519aba]",
  ts: "text-[#519aba]",
  tsx: "text-[#519aba]",
  js: "text-[#f4d13d]",
  jsx: "text-[#519aba]",
  md: "text-[#4ec9b0]",
  env: "text-[#b5cea8]",
  txt: "text-[#9cdcfe]",
  lock: "text-[#c586c0]",
};

function getFileAccent(name: string, language?: string) {
  if (language === "python") {
    return "text-sky-300";
  }
  const segments = name.toLowerCase().split(".");
  const extension = segments.length > 1 ? segments.pop() ?? "" : "";
  if (extension && FILE_ICON_COLORS[extension]) {
    return FILE_ICON_COLORS[extension];
  }
  return "text-slate-400";
}

function ChevronIcon({ open, tokens }: { readonly open: boolean; readonly tokens: ExplorerThemeTokens }) {
  return (
    <svg
      className={clsx("h-3 w-3 flex-shrink-0 transition-transform duration-150", open ? "rotate-90" : undefined)}
      viewBox="0 0 10 10"
      aria-hidden
    >
      <path
        d="M3 1l4 4-4 4"
        stroke={open ? tokens.chevronActive : tokens.chevronIdle}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FolderIcon({ open, tokens }: { readonly open: boolean; readonly tokens: ExplorerThemeTokens }) {
  return (
    <svg className="h-4 w-4 flex-shrink-0 transition-colors" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M3.5 5.5h4l1.5 1.5H16a1 1 0 0 1 1 1V15a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1Z"
        stroke={open ? tokens.folderIconActive : tokens.folderIcon}
        strokeWidth={1.4}
        strokeLinejoin="round"
        fill={open ? tokens.folderIconActive : "none"}
        opacity={open ? 0.25 : 1}
      />
    </svg>
  );
}

function FileIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={clsx("h-4 w-4 flex-shrink-0", className)} viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 3h4l4 4v9a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth={1.3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 3v4h4" stroke="currentColor" strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HideSidebarIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M3 3h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 13h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 8h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M11 5l2 3-2 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function MenuIconOpenFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3 4.5h3l1 1H13a1 1 0 0 1 1 1V12.5a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.2"
        fill="none"
      />
    </svg>
  );
}

function MenuIconCopyPath() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6 4.5h5.5a1 1 0 0 1 1 1V13"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <rect x="3.5" y="2.5" width="6" height="9" rx="1" stroke="currentColor" strokeWidth="1.1" fill="none" />
    </svg>
  );
}

function MenuIconCollapse() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 6l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIconNewFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4.5h4.5l3 3V13a1 1 0 0 1-1 1h-6.5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.2"
        fill="none"
      />
      <path d="M11 7.5h-2v-2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8.5 7.5h2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconNewFolder() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 5h3.5l1.2 1.4H12.5a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.2"
        fill="none"
        strokeLinejoin="round"
      />
      <path d="M8 8v3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M6.5 9.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconExpand() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 10l3-3 3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIconCollapseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M3 5h10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 8h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 11h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconDelete() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M6 3.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M4 4.5h8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path
        d="M5.5 4.5v7a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-7"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M6.5 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M9.5 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function CreateEntryRow({
  appearance,
  onSubmit,
  onCancel,
  onChange,
  isSubmitting,
  error,
  placeholder = "new_file.py",
  icon,
}: {
  readonly appearance: "light" | "dark";
  readonly onSubmit: (fileName: string) => void;
  readonly onCancel: () => void;
  readonly onChange?: () => void;
  readonly isSubmitting: boolean;
  readonly error: string | null;
  readonly placeholder?: string;
  readonly icon?: ReactNode;
}) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const handleSubmit = useCallback(() => {
    onSubmit(value.trim());
  }, [onSubmit, value]);

  const muted = appearance === "dark" ? "text-slate-300" : "text-slate-600";
  const bg = appearance === "dark" ? "#232323" : "#e8e8e8";
  const border = appearance === "dark" ? "#2f2f2f" : "#d4d4d4";

  return (
    <div
      className="rounded-md border px-2 py-1"
      style={{ backgroundColor: bg, borderColor: border }}
    >
      <div className="flex items-center gap-2">
        <span className="inline-flex w-4 justify-center text-[#4fc1ff]">{icon ?? <MenuIconNewFile />}</span>
        <input
          ref={inputRef}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            onChange?.();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              handleSubmit();
            }
            if (event.key === "Escape") {
              event.preventDefault();
              onCancel();
            }
          }}
          className="flex-1 rounded-sm border border-transparent bg-white/80 px-2 py-1 text-[13px] text-slate-900 outline-none focus:border-[#007acc]"
          placeholder={placeholder}
          disabled={isSubmitting}
        />
        <button
          type="button"
          className={clsx(
            "rounded-sm px-2 py-1 text-[12px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#007acc]",
            isSubmitting ? "cursor-wait bg-slate-300 text-slate-500" : "bg-[#007acc] text-white hover:bg-[#0e78c6]",
          )}
          onClick={handleSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          className="rounded-sm px-2 py-1 text-[12px] font-semibold text-slate-500 transition hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#007acc]"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancel
        </button>
      </div>
      <div className={clsx("mt-1 text-[11px]", muted)}>Enter a name and press Enter. Escape to cancel.</div>
      {error ? <div className="mt-1 text-[11px] font-semibold text-danger-500">{error}</div> : null}
    </div>
  );
}
