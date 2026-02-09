import type { FileListing } from "@/types/configurations";

import type { WorkbenchFileNode } from "../types";

const LANGUAGE_BY_EXTENSION: Record<string, string> = {
  json: "json",
  py: "python",
  ts: "typescript",
  tsx: "typescriptreact",
  js: "javascript",
  jsx: "javascriptreact",
  env: "dotenv",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
};

export function createWorkbenchTreeFromListing(listing: FileListing): WorkbenchFileNode | null {
  const rootId = listing.root || listing.prefix || listing.entries[0]?.parent || "";
  const hasEntries = listing.entries.length > 0;

  if (!rootId && !hasEntries) {
    return null;
  }

  const canonicalRootId = canonicalizePath(rootId);

  const rootNode: WorkbenchFileNode = {
    id: rootId,
    name: extractName(rootId),
    kind: "folder",
    children: [],
  };

  const nodes = new Map<string, WorkbenchFileNode>([[rootId, rootNode]]);

  const ensureFolder = (path: string): WorkbenchFileNode => {
    if (path.length === 0) {
      return rootNode;
    }
    const normalizedPath = canonicalizePath(path);
    const nodeId = normalizedPath === canonicalRootId ? rootId : normalizedPath;
    const existing = nodes.get(nodeId);
    if (existing) {
      return existing;
    }
    const folder: WorkbenchFileNode = {
      id: nodeId,
      name: extractName(nodeId),
      kind: "folder",
      children: [],
    };
    nodes.set(nodeId, folder);
    const parentPath = nodeId === rootId ? "" : deriveParent(nodeId) ?? rootId;
    const parentNode = ensureFolder(parentPath);
    addChild(parentNode, folder);
    return folder;
  };

  const sortedEntries = [...listing.entries].sort((a, b) => {
    if (a.depth !== b.depth) {
      return a.depth - b.depth;
    }
    return a.path.localeCompare(b.path);
  });

  for (const entry of sortedEntries) {
    const parentPath = entry.parent && entry.parent.length > 0 ? canonicalizePath(entry.parent) : rootId;
    const parentNode = ensureFolder(parentPath);

    if (entry.kind === "dir") {
      const folder = ensureFolder(entry.path);
      folder.name = entry.name;
      folder.metadata = {
        size: entry.size ?? null,
        modifiedAt: entry.mtime,
        contentType: entry.content_type,
        etag: entry.etag,
      };
      if (folder !== parentNode) {
        addChild(parentNode, folder);
      }
      continue;
    }

    const fileNode: WorkbenchFileNode = {
      id: entry.path,
      name: entry.name,
      kind: "file",
      language: inferLanguage(entry.path),
      metadata: {
        size: entry.size ?? null,
        modifiedAt: entry.mtime,
        contentType: entry.content_type,
        etag: entry.etag,
      },
    };
    nodes.set(entry.path, fileNode);
    addChild(parentNode, fileNode);
  }

  return rootNode;
}

function addChild(parent: WorkbenchFileNode, child: WorkbenchFileNode) {
  const existing = parent.children ?? [];
  const next = existing.some((node) => node.id === child.id)
    ? existing.map((node) => (node.id === child.id ? child : node))
    : [...existing, child];
  parent.children = next.sort(compareNodes);
}

function compareNodes(a: WorkbenchFileNode, b: WorkbenchFileNode): number {
  if (a.kind !== b.kind) {
    return a.kind === "folder" ? -1 : 1;
  }
  return a.name.localeCompare(b.name);
}

function inferLanguage(path: string): string | undefined {
  const normalized = path.toLowerCase();
  const extensionIndex = normalized.lastIndexOf(".");
  if (extensionIndex === -1) {
    return undefined;
  }
  const extension = normalized.slice(extensionIndex + 1);
  return LANGUAGE_BY_EXTENSION[extension];
}

function extractName(path: string): string {
  const normalized = canonicalizePath(path);
  if (!normalized) {
    return "";
  }
  const index = normalized.lastIndexOf("/");
  return index >= 0 ? normalized.slice(index + 1) : normalized;
}

function deriveParent(path: string): string | undefined {
  const normalized = canonicalizePath(path);
  if (!normalized) {
    return undefined;
  }
  const index = normalized.lastIndexOf("/");
  if (index === -1) {
    return "";
  }
  return normalized.slice(0, index);
}

function canonicalizePath(path: string): string {
  if (!path) {
    return "";
  }
  return path.replace(/\/+$/, "");
}

export function findFileNode(root: WorkbenchFileNode, id: string): WorkbenchFileNode | null {
  if (root.id === id) {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const match = findFileNode(child, id);
    if (match) {
      return match;
    }
  }
  return null;
}

export function findFirstFile(root: WorkbenchFileNode): WorkbenchFileNode | null {
  if (root.kind === "file") {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const file = findFirstFile(child);
    if (file) {
      return file;
    }
  }
  return null;
}
