import type { AdapterWriteOptions, FileBuffer, FileNode, RunResult, ValidationResult } from "./types";

export interface ConfigFsAdapter {
  listTree(): Promise<FileNode[]>;
  readFile(path: string): Promise<FileBuffer>;
  writeFile(buffer: FileBuffer, options?: AdapterWriteOptions): Promise<FileBuffer>;
  renamePath(fromPath: string, toPath: string): Promise<void>;
  deletePath(path: string): Promise<void>;
  validate(target?: { readonly path?: string }): Promise<ValidationResult>;
  run(target?: { readonly path?: string }): Promise<RunResult>;
}
