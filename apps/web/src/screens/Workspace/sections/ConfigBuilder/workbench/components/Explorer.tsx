import { useCallback, useEffect, useMemo, useState } from "react";

import clsx from "clsx";

import type { WorkbenchFileNode } from "../types";

interface ExplorerProps {
  readonly width: number;
  readonly tree: WorkbenchFileNode;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onSelectFile: (fileId: string) => void;
}

export function Explorer({ width, tree, activeFileId, openFileIds, onSelectFile }: ExplorerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set([tree.id]));

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

  const rootChildren = useMemo(() => tree.children ?? [], [tree]);

  return (
    <aside className="flex h-full min-h-0 flex-col bg-slate-50" style={{ width }} aria-label="Config files explorer">
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Explorer</h2>
      </div>
      <nav className="flex-1 overflow-auto px-2 py-2 text-sm">
        <ul className="space-y-1">
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
            />
          ))}
        </ul>
      </nav>
    </aside>
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
}

function ExplorerNode({
  node,
  depth,
  expanded,
  activeFileId,
  openFileIds,
  onToggleFolder,
  onSelectFile,
}: ExplorerNodeProps) {
  const paddingLeft = 12 + depth * 12;

  if (node.kind === "folder") {
    const isOpen = expanded.has(node.id);
    return (
      <li>
        <button
          type="button"
          onClick={() => onToggleFolder(node.id)}
          className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-slate-700 hover:bg-slate-200"
          style={{ paddingLeft }}
        >
          <span className="text-xs uppercase tracking-wide text-slate-500">{isOpen ? "▾" : "▸"}</span>
          <span>{node.name}</span>
        </button>
        {isOpen && node.children?.length ? (
          <ul className="mt-1 space-y-1">
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
              />
            ))}
          </ul>
        ) : null}
      </li>
    );
  }

  const isActive = activeFileId === node.id;
  const isOpen = openFileIds.includes(node.id);

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelectFile(node.id)}
        className={clsx(
          "flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-slate-200",
          isActive ? "bg-slate-200 font-medium text-slate-900" : "text-slate-700",
        )}
        style={{ paddingLeft }}
      >
        <span className="text-xs text-slate-400">{isOpen ? "●" : "○"}</span>
        <span>{node.name}</span>
      </button>
    </li>
  );
}
