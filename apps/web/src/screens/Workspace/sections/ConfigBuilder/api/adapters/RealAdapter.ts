import type { ConfigFsAdapter } from "./ConfigFsAdapter";
import type { AdapterWriteOptions, FileBuffer, FileNode, RunResult, ValidationResult } from "./types";

export class RealAdapter implements ConfigFsAdapter {
  constructor(private readonly options: { workspaceId: string; configId: string }) {}

  async listTree(): Promise<FileNode[]> {
    throw new Error("RealAdapter is not implemented in the demo build.");
  }

  async readFile(path: string): Promise<FileBuffer> {
    throw new Error(`RealAdapter.readFile(${path}) is not implemented in the demo build.`);
  }

  async writeFile(buffer: FileBuffer, _options?: AdapterWriteOptions): Promise<FileBuffer> {
    throw new Error(`RealAdapter.writeFile(${buffer.path}) is not implemented in the demo build.`);
  }

  async renamePath(_fromPath: string, _toPath: string): Promise<void> {
    throw new Error("RealAdapter.renamePath is not implemented in the demo build.");
  }

  async deletePath(_path: string): Promise<void> {
    throw new Error("RealAdapter.deletePath is not implemented in the demo build.");
  }

  async validate(_target?: { readonly path?: string }): Promise<ValidationResult> {
    throw new Error("RealAdapter.validate is not implemented in the demo build.");
  }

  async run(_target?: { readonly path?: string }): Promise<RunResult> {
    throw new Error("RealAdapter.run is not implemented in the demo build.");
  }
}
