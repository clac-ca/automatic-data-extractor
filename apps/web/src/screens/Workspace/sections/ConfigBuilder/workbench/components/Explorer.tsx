import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import clsx from "clsx";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";

import type { WorkbenchFileNode } from "../types";

type ExplorerTheme = "light" | "dark";

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

interface ExplorerProps {
  readonly width: number;
  readonly tree: WorkbenchFileNode;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onSelectFile: (fileId: string) => void;
  readonly theme: ExplorerTheme;
  readonly onCloseFile: (fileId: string) => void;
  readonly onCloseOtherFiles: (fileId: string) => void;
  readonly onCloseTabsToRight: (fileId: string) => void;
  readonly onCloseAllFiles: () => void;
  readonly onHide: () => void;
}

export function Explorer({
  width,
  tree,
  activeFileId,
  openFileIds,
  onSelectFile,
  theme,
  onCloseFile,
  onCloseOtherFiles,
  onCloseTabsToRight,
  onCloseAllFiles,
  onHide,
}: ExplorerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set([tree.id]));
  const [contextMenu, setContextMenu] = useState<{
    readonly node: WorkbenchFileNode;
    readonly position: { readonly x: number; readonly y: number };
  } | null>(null);

  useEffect(() => {
    setExpanded(new Set([tree.id]));
  }, [tree.id]);

  const toggleFolder = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const setFolderExpanded = useCallback(
    (nodeId: string, nextExpanded: boolean) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (nextExpanded) {
          next.add(nodeId);
        } else if (nodeId !== tree.id) {
          next.delete(nodeId);
        }
        if (!next.has(tree.id)) {
          next.add(tree.id);
        }
        return next;
      });
    },
    [tree.id],
  );

  const collapseAll = useCallback(() => {
    setExpanded(new Set([tree.id]));
  }, [tree.id]);

  const rootChildren = useMemo(() => tree.children ?? [], [tree]);
  const menuAppearance = theme === "dark" ? "dark" : "light";

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: WorkbenchFileNode) => {
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

  const explorerMenuItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const node = contextMenu.node;
    const shortcuts = {
      open: "Enter",
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
      copyPath: "Ctrl+K Ctrl+C",
      collapseAll: "Ctrl+K Ctrl+0",
    };
    if (node.kind === "file") {
      const isOpen = openFileIds.includes(node.id);
      const openCount = openFileIds.length;
      const tabIndex = openFileIds.indexOf(node.id);
      const hasTabsToRight = tabIndex >= 0 && tabIndex < openCount - 1;
      return [
        { id: "open-file", label: "Open", icon: <MenuIconOpenFile />, shortcut: shortcuts.open, onSelect: () => onSelectFile(node.id) },
        {
          id: "close-file",
          label: "Close",
          icon: <MenuIconClose />,
          disabled: !isOpen,
          shortcut: shortcuts.close,
          onSelect: () => onCloseFile(node.id),
        },
        {
          id: "close-file-others",
          label: "Close Others",
          icon: <MenuIconCloseOthers />,
          disabled: !isOpen || openCount <= 1,
          shortcut: shortcuts.closeOthers,
          onSelect: () => onCloseOtherFiles(node.id),
        },
        {
          id: "close-file-right",
          label: "Close Tabs to the Right",
          icon: <MenuIconCloseRight />,
          disabled: !isOpen || !hasTabsToRight,
          shortcut: shortcuts.closeRight,
          onSelect: () => onCloseTabsToRight(node.id),
        },
        {
          id: "close-file-all",
          label: "Close All",
          dividerAbove: true,
          disabled: openCount === 0,
          icon: <MenuIconCloseAll />,
          shortcut: shortcuts.closeAll,
          onSelect: () => onCloseAllFiles(),
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
      ];
    }
    const isExpanded = expanded.has(node.id);
    return [
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
    ];
  }, [
    contextMenu,
    openFileIds,
    onSelectFile,
    onCloseFile,
    onCloseOtherFiles,
    onCloseTabsToRight,
    onCloseAllFiles,
    handleCopyPath,
    expanded,
    setFolderExpanded,
    collapseAll,
  ]);
  const tokens = EXPLORER_THEME_TOKENS[theme];
  const focusRingClass = FOCUS_RING_CLASS[theme];

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
                focusRingClass={focusRingClass}
                onContextMenu={handleNodeContextMenu}
              />
            ))}
          </ul>
        </nav>
      </aside>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu && contextMenu.position}
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
  readonly focusRingClass: string;
  readonly onContextMenu: (event: React.MouseEvent, node: WorkbenchFileNode) => void;
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
  focusRingClass,
  onContextMenu,
}: ExplorerNodeProps) {
  const paddingLeft = 8 + depth * 16;
  const baseStyle: CSSProperties = {
    paddingLeft,
    ["--tree-hover-bg" as const]: tokens.rowHover,
  };

  if (node.kind === "folder") {
    const isOpen = expanded.has(node.id);
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
          )}
          style={folderStyle}
          aria-expanded={isOpen}
        >
          <ChevronIcon open={isOpen} tokens={tokens} />
          <FolderIcon open={isOpen} tokens={tokens} />
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen && node.children?.length ? (
          <ul className="mt-0.5 space-y-0.5">
            {node.children.map((child) => (
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
              focusRingClass={focusRingClass}
              onContextMenu={onContextMenu}
            />
            ))}
          </ul>
        ) : null}
      </li>
    );
  }

  const isActive = activeFileId === node.id;
  const isOpen = openFileIds.includes(node.id);
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
        )}
        style={fileStyle}
      >
        <span className="inline-flex w-4 justify-center">
          <FileIcon className={fileAccent} />
        </span>
        <span className="flex-1 truncate">{node.name}</span>
        {isActive ? (
          <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: tokens.badgeActive }}>
            Active
          </span>
        ) : isOpen ? (
          <span className="text-[9px] uppercase tracking-wide" style={{ color: tokens.badgeOpen }}>
            Open
          </span>
        ) : null}
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
      className={clsx(
        "h-3 w-3 flex-shrink-0 transition-transform duration-150",
        open ? "rotate-90" : undefined,
      )}
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

function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4.5h3.5a1 1 0 0 1 1 1V13M12.5 11.5h-3.5a1 1 0 0 1-1-1V3"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <path d="M4.5 6.5l7 7m0-7-7 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
