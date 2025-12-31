import type { WorkbenchUploadFile } from "../types";

import { normalizeWorkbenchPath } from "./paths";

export function hasFileDrag(dataTransfer: DataTransfer | null | undefined) {
  if (!dataTransfer) {
    return false;
  }
  return Array.from(dataTransfer.types ?? []).includes("Files");
}

type FileSystemEntryLike = {
  readonly isFile: boolean;
  readonly isDirectory: boolean;
  readonly name: string;
  readonly fullPath?: string;
  file?: (callback: (file: File) => void, errorCallback?: (error: unknown) => void) => void;
  createReader?: () => { readEntries: (success: (entries: FileSystemEntryLike[]) => void, failure?: (error: unknown) => void) => void };
};

export async function extractDroppedFiles(dataTransfer: DataTransfer): Promise<WorkbenchUploadFile[]> {
  const items = Array.from(dataTransfer.items ?? []);
  const entries = items
    .filter((item) => item.kind === "file")
    .map((item) => (item as unknown as { webkitGetAsEntry?: () => FileSystemEntryLike | null }).webkitGetAsEntry?.() ?? null)
    .filter((entry): entry is FileSystemEntryLike => Boolean(entry));

  if (entries.length > 0) {
    const results = await Promise.all(entries.map((entry) => walkFileEntry(entry)));
    return results.flat();
  }

  return Array.from(dataTransfer.files ?? [])
    .filter((file) => Boolean(file))
    .map((file) => ({ file, relativePath: file.name }));
}

async function walkFileEntry(entry: FileSystemEntryLike): Promise<WorkbenchUploadFile[]> {
  if (entry.isFile) {
    try {
      const file = await new Promise<File>((resolve, reject) => {
        if (!entry.file) {
          reject(new Error("Dropped file entry is missing a file() reader."));
          return;
        }
        entry.file(resolve, reject);
      });
      const relativePath = normalizeDroppedPath(entry.fullPath || file.name);
      if (!relativePath) {
        return [];
      }
      return [{ file, relativePath }];
    } catch {
      return [];
    }
  }

  if (!entry.isDirectory || !entry.createReader) {
    return [];
  }

  const reader = entry.createReader();
  const children = await readAllDirectoryEntries(reader);
  const results = await Promise.all(children.map((child) => walkFileEntry(child)));
  return results.flat();
}

async function readAllDirectoryEntries(reader: {
  readEntries: (success: (entries: FileSystemEntryLike[]) => void, failure?: (error: unknown) => void) => void;
}): Promise<FileSystemEntryLike[]> {
  const all: FileSystemEntryLike[] = [];

  while (true) {
    const entries = await new Promise<FileSystemEntryLike[]>((resolve, reject) =>
      reader.readEntries(resolve, reject),
    );
    if (!entries.length) {
      break;
    }
    all.push(...entries);
  }

  return all;
}

function normalizeDroppedPath(path: string) {
  return normalizeWorkbenchPath(path);
}

