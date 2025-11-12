import { useEffect, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react";

import type { FileNode } from "../adapters/types";

interface ExplorerTreeProps {
  readonly nodes: readonly FileNode[];
  readonly activePath: string | null;
  readonly onOpenPath: (path: string) => void;
  readonly onRenamePath: (path: string) => void;
  readonly onDeletePath: (path: string) => void;
  readonly onDownloadPath: (path: string) => void;
}

interface FlattenedNode {
  readonly node: FileNode;
  readonly depth: number;
}

interface ContextMenuState {
  readonly path: string;
  readonly x: number;
  readonly y: number;
  readonly kind: "file" | "folder";
}

export function ExplorerTree({
  nodes,
  activePath,
  onOpenPath,
  onRenamePath,
  onDeletePath,
  onDownloadPath,
}: ExplorerTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(nodes.map((node) => node.path)));
  const [focusedPath, setFocusedPath] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);

  useEffect(() => {
    setExpanded((prev) => {
      if (prev.size > 0) {
        return prev;
      }
      return new Set(nodes.map((node) => node.path));
    });
  }, [nodes]);

  const flattened = useMemo(() => flatten(nodes, expanded), [nodes, expanded]);

  useEffect(() => {
    if (activePath) {
      setFocusedPath(activePath);
    }
  }, [activePath]);

  const handleToggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (flattened.length === 0) {
      return;
    }
    const currentIndex = focusedPath ? flattened.findIndex((item) => item.node.path === focusedPath) : -1;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const nextIndex = Math.min(flattened.length - 1, currentIndex + 1);
      const nextItem = flattened[nextIndex];
      if (nextItem) {
        setFocusedPath(nextItem.node.path);
      }
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      const nextIndex = Math.max(0, currentIndex <= 0 ? 0 : currentIndex - 1);
      const nextItem = flattened[nextIndex];
      if (nextItem) {
        setFocusedPath(nextItem.node.path);
      }
    }
    if (event.key === "ArrowRight" && focusedPath) {
      event.preventDefault();
      const item = flattened.find((entry) => entry.node.path === focusedPath);
      if (item?.node.kind === "folder") {
        if (!expanded.has(item.node.path)) {
          handleToggle(item.node.path);
        } else if (item.node.children.length > 0) {
          setFocusedPath(item.node.children[0].path);
        }
      }
    }
    if (event.key === "ArrowLeft" && focusedPath) {
      event.preventDefault();
      const item = flattened.find((entry) => entry.node.path === focusedPath);
      if (item?.node.kind === "folder" && expanded.has(item.node.path)) {
        handleToggle(item.node.path);
      } else {
        const parentPath = item?.node.parent;
        if (parentPath) {
          setFocusedPath(parentPath);
        }
      }
    }
    if (event.key === "Enter" && focusedPath) {
      event.preventDefault();
      const item = flattened.find((entry) => entry.node.path === focusedPath);
      if (!item) {
        return;
      }
      if (item.node.kind === "folder") {
        handleToggle(item.node.path);
      } else {
        onOpenPath(item.node.path);
      }
    }
  };

  const handleContextMenu = (event: MouseEvent<HTMLElement>, node: FileNode) => {
    event.preventDefault();
    setContextMenu({ path: node.path, x: event.clientX, y: event.clientY, kind: node.kind });
  };

  useEffect(() => {
    if (!contextMenu) {
      return;
    }
    const handleClick = () => setContextMenu(null);
    window.addEventListener("mousedown", handleClick);
    return () => window.removeEventListener("mousedown", handleClick);
  }, [contextMenu]);

  return (
    <div
      className="flex h-full flex-col"
      role="tree"
      aria-label="Config package files"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <ul className="flex-1 overflow-y-auto py-2">
        {flattened.map(({ node, depth }) => {
          const isFolder = node.kind === "folder";
          const isExpanded = expanded.has(node.path);
          const isActive = node.path === activePath;
          return (
            <li key={node.path}>
              <button
                type="button"
                role="treeitem"
                aria-level={depth + 1}
                aria-expanded={isFolder ? isExpanded : undefined}
                aria-selected={isActive}
                onClick={() => (isFolder ? handleToggle(node.path) : onOpenPath(node.path))}
                onContextMenu={(event) => handleContextMenu(event, node)}
                onFocus={() => setFocusedPath(node.path)}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                  isActive ? "bg-brand-500/20 text-white" : "text-slate-200 hover:bg-slate-800/60"
                }`}
                style={{ paddingLeft: `${depth * 14 + 12}px` }}
              >
                <span className="text-xs text-slate-400">{isFolder ? (isExpanded ? "▾" : "▸") : "•"}</span>
                <span className="truncate">{node.name}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {contextMenu ? (
        <div
          className="fixed z-50 min-w-[160px] rounded-xl border border-slate-700 bg-slate-900/95 p-1 text-sm text-slate-200 shadow-xl"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          role="menu"
        >
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-slate-800"
            onClick={() => {
              onRenamePath(contextMenu.path);
              setContextMenu(null);
            }}
          >
            Rename
            <span className="text-xs text-slate-500">↵</span>
          </button>
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-slate-800"
            onClick={() => {
              onDeletePath(contextMenu.path);
              setContextMenu(null);
            }}
          >
            Delete
          </button>
          {contextMenu.kind === "file" ? (
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-slate-800"
              onClick={() => {
                onDownloadPath(contextMenu.path);
                setContextMenu(null);
              }}
            >
              Download
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function flatten(nodes: readonly FileNode[], expanded: ReadonlySet<string>, depth = 0): FlattenedNode[] {
  const items: FlattenedNode[] = [];
  nodes.forEach((node) => {
    items.push({ node, depth });
    if (node.kind === "folder" && expanded.has(node.path)) {
      items.push(...flatten(node.children, expanded, depth + 1));
    }
  });
  return items;
}
