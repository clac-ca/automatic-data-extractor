import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent as ReactDragEvent,
  type MouseEvent,
  type ReactNode,
} from "react";

import clsx from "clsx";

import { ContextMenu, type ContextMenuItem } from "@/components/ui/context-menu";
import {
  ChevronDownSmallIcon,
  ChevronRightTinyIcon,
  ChevronUpSmallIcon,
  CollapseAllIcon,
  CopyPathIcon,
  DeleteIcon,
  FileIcon,
  FolderIcon,
  HideSidebarIcon,
  NewFileIcon,
  NewFolderIcon,
  OpenFileIcon,
  UploadIcon,
} from "@components/icons";
import { createScopedStorage } from "@lib/storage";

import type { WorkbenchFileNode, WorkbenchUploadFile } from "../types";
import { extractDroppedFiles, hasFileDrag } from "../utils/fileDrop";

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

const EXPLORER_TOKENS: ExplorerThemeTokens = {
  surface: "var(--card)",
  border: "var(--border)",
  heading: "var(--foreground)",
  label: "var(--muted-foreground)",
  textPrimary: "var(--foreground)",
  textMuted: "var(--muted-foreground)",
  rowHover: "var(--muted)",
  folderActiveBg: "transparent",
  selectionBg: "var(--muted)",
  selectionText: "var(--foreground)",
  badgeActive: "var(--ring)",
  badgeOpen: "var(--muted-foreground)",
  folderIcon: "var(--ring)",
  folderIconActive: "var(--ring)",
  chevronIdle: "var(--muted-foreground)",
  chevronActive: "var(--foreground)",
};

const EXPLORER_THEME_TOKENS: Record<ExplorerTheme, ExplorerThemeTokens> = {
  dark: EXPLORER_TOKENS,
  light: EXPLORER_TOKENS,
};

const FOCUS_RING_CLASS = "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card";

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
  readonly canUploadFiles?: boolean;
  readonly onUploadFiles?: (folderPath: string, files: readonly WorkbenchUploadFile[]) => void | Promise<void>;
  readonly isUploadingFiles?: boolean;
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
  canUploadFiles = false,
  onUploadFiles,
  isUploadingFiles = false,
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
  const nodeLookup = useMemo(() => {
    const nodes = new Map<string, WorkbenchFileNode>();
    const visit = (node: WorkbenchFileNode) => {
      nodes.set(node.id, node);
      node.children?.forEach(visit);
    };
    visit(tree);
    return nodes;
  }, [tree]);
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
  const [dropActive, setDropActive] = useState(false);
  const [dropTarget, setDropTarget] = useState<{ readonly folderPath: string; readonly rowId: string } | null>(null);
  const dragCounterRef = useRef(0);
  const autoExpandTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastAutoExpandTargetRef = useRef<string | null>(null);

  useEffect(() => {
    setEditing(null);
    setCreateError(null);
    setDropTarget(null);
    setDropActive(false);
    dragCounterRef.current = 0;
    lastAutoExpandTargetRef.current = null;
    if (autoExpandTimeoutRef.current) {
      clearTimeout(autoExpandTimeoutRef.current);
      autoExpandTimeoutRef.current = null;
    }
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

  const clearAutoExpand = useCallback(() => {
    if (autoExpandTimeoutRef.current) {
      clearTimeout(autoExpandTimeoutRef.current);
      autoExpandTimeoutRef.current = null;
    }
    lastAutoExpandTargetRef.current = null;
  }, []);

  const resolveDropTarget = useCallback(
    (target: EventTarget | null): { folderPath: string; rowId: string } => {
      const element = (target as HTMLElement | null)?.closest?.("[data-explorer-drop-row]") as HTMLElement | null;
      const folderPath = element?.dataset.explorerDropPath ?? "";
      const rowId = element?.dataset.explorerDropRow ?? tree.id;
      return { folderPath: folderPath === tree.id ? "" : folderPath, rowId };
    },
    [tree.id],
  );

  const handleDragEnter = useCallback((event: ReactDragEvent<HTMLElement>) => {
    if (!hasFileDrag(event.dataTransfer)) {
      return;
    }
    dragCounterRef.current += 1;
    setDropActive(true);
  }, []);

  const handleDragLeave = useCallback(
    (_event: ReactDragEvent<HTMLElement>) => {
      if (!dropActive) {
        return;
      }
      dragCounterRef.current = Math.max(0, dragCounterRef.current - 1);
      if (dragCounterRef.current === 0) {
        setDropActive(false);
        setDropTarget(null);
        clearAutoExpand();
      }
    },
    [clearAutoExpand, dropActive],
  );

  const handleDragOver = useCallback(
    (event: ReactDragEvent<HTMLElement>) => {
      if (!hasFileDrag(event.dataTransfer)) {
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = canUploadFiles && onUploadFiles && !isUploadingFiles ? "copy" : "none";
      if (!dropActive) {
        setDropActive(true);
      }

      const nextTarget = resolveDropTarget(event.target);
      setDropTarget((prev) => (prev?.rowId === nextTarget.rowId && prev.folderPath === nextTarget.folderPath ? prev : nextTarget));

      const hoveredNode = nodeLookup.get(nextTarget.rowId);
      if (!hoveredNode || hoveredNode.kind !== "folder") {
        clearAutoExpand();
        return;
      }
      if (expanded.has(hoveredNode.id)) {
        clearAutoExpand();
        return;
      }
      if (lastAutoExpandTargetRef.current === hoveredNode.id && autoExpandTimeoutRef.current) {
        return;
      }
      clearAutoExpand();
      lastAutoExpandTargetRef.current = hoveredNode.id;
      autoExpandTimeoutRef.current = setTimeout(() => {
        setFolderExpanded(hoveredNode.id, true);
        clearAutoExpand();
      }, 650);
    },
    [
      canUploadFiles,
      clearAutoExpand,
      dropActive,
      expanded,
      isUploadingFiles,
      nodeLookup,
      onUploadFiles,
      resolveDropTarget,
      setFolderExpanded,
    ],
  );

  const handleDrop = useCallback(
    async (event: ReactDragEvent<HTMLElement>) => {
      if (!hasFileDrag(event.dataTransfer)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setDropActive(false);
      setDropTarget(null);
      dragCounterRef.current = 0;
      clearAutoExpand();

      const files = await extractDroppedFiles(event.dataTransfer);
      if (!canUploadFiles || !onUploadFiles || isUploadingFiles || files.length === 0) {
        return;
      }
      const target = resolveDropTarget(event.target);
      void onUploadFiles(target.folderPath, files);
    },
    [canUploadFiles, clearAutoExpand, isUploadingFiles, onUploadFiles, resolveDropTarget],
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
        { id: "open-file", label: "Open", icon: <OpenFileIcon className={MENU_ICON_CLASS} />, shortcut: shortcuts.open, onSelect: () => onSelectFile(node.id) },
        {
          id: "copy-path",
          label: "Copy Path",
          dividerAbove: true,
          icon: <CopyPathIcon className={MENU_ICON_CLASS} />,
          shortcut: shortcuts.copyPath,
          onSelect: () => {
            void handleCopyPath(node.id);
          },
        },
        {
          id: "delete-file",
          label: "Delete",
          icon: <DeleteIcon className={MENU_ICON_CLASS} />,
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
        icon: <NewFileIcon className={MENU_ICON_CLASS} />,
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
        icon: <NewFolderIcon className={MENU_ICON_CLASS} />,
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
        icon: isExpanded ? <ChevronDownSmallIcon className={MENU_ICON_CLASS} /> : <ChevronUpSmallIcon className={MENU_ICON_CLASS} />,
        onSelect: () => setFolderExpanded(node.id, !isExpanded),
      },
      {
        id: "collapse-all",
        label: "Collapse All",
        icon: <CollapseAllIcon className={MENU_ICON_CLASS} />,
        shortcut: shortcuts.collapseAll,
        dividerAbove: true,
        onSelect: () => collapseAll(),
      },
      {
        id: "copy-path",
        label: "Copy Path",
        dividerAbove: true,
        icon: <CopyPathIcon className={MENU_ICON_CLASS} />,
        shortcut: shortcuts.copyPath,
        onSelect: () => {
          void handleCopyPath(node.id);
        },
      },
      {
        id: "delete-folder",
        label: "Delete Folder",
        icon: <DeleteIcon className={MENU_ICON_CLASS} />,
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
  const focusRingClass = FOCUS_RING_CLASS;
  const rootChildren = useMemo(() => tree.children ?? [], [tree]);
  const menuAppearance = theme === "dark" ? "dark" : "light";
  const dropTargetLabel = useMemo(() => {
    if (!dropActive) {
      return null;
    }
    const folderPath = dropTarget?.folderPath ?? "";
    if (!folderPath) {
      return "root";
    }
    return folderPath;
  }, [dropActive, dropTarget?.folderPath]);
  const canDropUpload = canUploadFiles && Boolean(onUploadFiles) && !isUploadingFiles;

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
          style={{ borderColor: tokens.border, backgroundColor: tokens.rowHover }}
        >
          <div className="flex items-center gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-[0.3em]" style={{ color: tokens.heading }}>
              Explorer
            </div>
            {isUploadingFiles ? (
              <div className="flex items-center gap-1 text-[11px]" style={{ color: tokens.label }}>
                <span className="inline-flex h-2.5 w-2.5 animate-spin rounded-full border border-current border-t-transparent" aria-hidden />
                <span className="font-medium">Uploading…</span>
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onHide}
            aria-label="Hide explorer"
            className={clsx(
              "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "hover:bg-muted hover:text-foreground",
            )}
          >
            <HideSidebarIcon className="h-3.5 w-3.5" />
          </button>
        </div>
        <nav
          className="relative flex-1 overflow-auto px-2 py-2"
          aria-label="Workspace files tree"
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <ul className="space-y-0.5">
            {rootChildren.map((node) => (
              <ExplorerNode
                key={node.id}
                node={node}
                parentId={tree.id}
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
                dropActive={dropActive}
                dropTargetRowId={dropTarget?.rowId ?? null}
              />
            ))}
            {editing?.parentId === tree.id ? (
              <li className="pl-2">
                <CreateEntryRow
                  appearance={theme}
                  icon={editing.kind === "folder" ? <NewFolderIcon className={MENU_ICON_CLASS} /> : undefined}
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
          {dropActive ? (
            <div
              className={clsx(
                "pointer-events-none absolute inset-2 rounded-xl border border-dashed bg-card/85 p-3 transition",
                canDropUpload ? "opacity-100" : "opacity-90",
              )}
              style={{
                borderColor: tokens.badgeActive,
              }}
              aria-hidden={!dropActive}
            >
              <div className="flex items-center gap-3">
                <span
                  className={clsx(
                    "inline-flex h-9 w-9 items-center justify-center rounded-full border border-border/60 bg-card/80",
                  )}
                  style={{ color: tokens.badgeActive }}
                >
                  <UploadIcon className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold" style={{ color: tokens.textPrimary }}>
                    {canDropUpload ? "Drop to upload" : "Upload disabled"}
                  </p>
                  <p className="mt-0.5 text-[12px]" style={{ color: tokens.textMuted }}>
                    {canDropUpload ? (
                      <>
                        Upload to <span className="font-semibold">{dropTargetLabel}</span>
                      </>
                    ) : (
                      isUploadingFiles
                        ? "Uploads are in progress."
                        : "Uploads aren’t available right now."
                    )}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
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
  readonly parentId: string;
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
  readonly dropActive: boolean;
  readonly dropTargetRowId: string | null;
}

function ExplorerNode({
  node,
  parentId,
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
  dropActive,
  dropTargetRowId,
}: ExplorerNodeProps) {
  const paddingLeft = 8 + depth * 16;
  const baseStyle: CSSProperties & { ["--tree-hover-bg"]?: string } = {
    paddingLeft,
    ["--tree-hover-bg"]: tokens.rowHover,
  };

  const isDropTargetRow = dropActive && dropTargetRowId === node.id;

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

    if (isDropTargetRow) {
      folderStyle.outline = `1px dashed ${tokens.badgeActive}`;
      folderStyle.outlineOffset = -1;
      folderStyle.backgroundColor = tokens.rowHover;
    }

    return (
      <li className="relative">
        <button
          type="button"
          onClick={() => onToggleFolder(node.id)}
          onContextMenu={(event) => onContextMenu(event, node)}
          data-explorer-drop-row={node.id}
          data-explorer-drop-path={node.id}
          className={clsx(
            "group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-medium transition hover:bg-[var(--tree-hover-bg)]",
            focusRingClass,
            isDeleting && "opacity-60",
          )}
          style={folderStyle}
          aria-expanded={isOpen}
          disabled={isDeleting}
        >
          <ChevronRightTinyIcon
            className={clsx("h-3 w-3 flex-shrink-0 transition-transform duration-150", isOpen ? "rotate-90" : undefined)}
            stroke={isOpen ? tokens.chevronActive : tokens.chevronIdle}
          />
          <FolderIcon
            className="h-4 w-4 flex-shrink-0 transition-colors"
            stroke={isOpen ? tokens.folderIconActive : tokens.folderIcon}
            fill={isOpen ? tokens.folderIconActive : "none"}
            opacity={isOpen ? 0.25 : 1}
          />
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen ? (
          <ul className="mt-0.5 space-y-0.5">
            {node.children?.map((child) => (
              <ExplorerNode
                key={child.id}
                node={child}
                parentId={node.id}
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
                dropActive={dropActive}
                dropTargetRowId={dropTargetRowId}
              />
            ))}
            {isEditingHere ? (
              <li className="pl-2">
                <CreateEntryRow
                  appearance={theme}
                  icon={editing?.kind === "folder" ? <NewFolderIcon className={MENU_ICON_CLASS} /> : undefined}
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
  if (isDropTargetRow) {
    fileStyle.outline = `1px dashed ${tokens.badgeActive}`;
    fileStyle.outlineOffset = -1;
    if (!isActive) {
      fileStyle.backgroundColor = tokens.rowHover;
    }
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelectFile(node.id)}
        onContextMenu={(event) => onContextMenu(event, node)}
        data-explorer-drop-row={node.id}
        data-explorer-drop-path={parentId}
        className={clsx(
          "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition hover:bg-[var(--tree-hover-bg)]",
          focusRingClass,
          isActive && "shadow-inner",
          isDeleting && "opacity-60",
        )}
        style={fileStyle}
        disabled={isDeleting}
      >
        <span className="inline-flex w-4 justify-center">
          <FileIcon
            className={clsx(
              "h-4 w-4 flex-shrink-0",
              fileAccent,
              isOpen && !isActive && "opacity-90",
              !isOpen && !isActive && "opacity-75",
            )}
          />
        </span>
        <span className={clsx("flex-1 truncate", isActive && "font-semibold")}>{node.name}</span>
        {isOpen && !isActive ? <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: tokens.badgeOpen }} /> : null}
      </button>
    </li>
  );
}

const FILE_ICON_COLORS: Record<string, string> = {
  json: "text-filetype-json",
  py: "text-filetype-py",
  ts: "text-filetype-ts",
  tsx: "text-filetype-tsx",
  js: "text-filetype-js",
  jsx: "text-filetype-jsx",
  md: "text-filetype-md",
  env: "text-filetype-env",
  txt: "text-filetype-txt",
  lock: "text-filetype-lock",
};

function getFileAccent(name: string, language?: string) {
  if (language === "python") {
    return "text-filetype-py";
  }
  const segments = name.toLowerCase().split(".");
  const extension = segments.length > 1 ? segments.pop() ?? "" : "";
  if (extension && FILE_ICON_COLORS[extension]) {
    return FILE_ICON_COLORS[extension];
  }
  return "text-muted-foreground";
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function CreateEntryRow({
  appearance: _appearance,
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

  const muted = "text-muted-foreground";

  return (
    <div className="rounded-md border border-border bg-muted px-2 py-1">
      <div className="flex items-center gap-2">
        <span className="inline-flex w-4 justify-center text-foreground">{icon ?? <NewFileIcon className={MENU_ICON_CLASS} />}</span>
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
          className="flex-1 rounded-sm border border-transparent bg-card/80 px-2 py-1 text-[13px] text-foreground outline-none focus:border-ring"
          placeholder={placeholder}
          disabled={isSubmitting}
        />
        <button
          type="button"
          className={clsx(
            "rounded-sm px-2 py-1 text-[12px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            isSubmitting ? "cursor-wait bg-muted text-muted-foreground" : "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
          onClick={handleSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          className="rounded-sm px-2 py-1 text-[12px] font-semibold text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancel
        </button>
      </div>
      <div className={clsx("mt-1 text-[11px]", muted)}>Enter a name and press Enter. Escape to cancel.</div>
      {error ? <div className="mt-1 text-[11px] font-semibold text-destructive">{error}</div> : null}
    </div>
  );
}
