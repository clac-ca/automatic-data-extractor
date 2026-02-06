import type { components } from "@/types";

export type ConfigurationPage = components["schemas"]["ConfigurationPage"];
export type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];
export type ConfigurationValidateResponse = components["schemas"]["ConfigurationValidateResponse"];

export type FileEntry = components["schemas"]["FileEntry"];
export type FileListing = components["schemas"]["FileListing"];
export type FileReadJson = {
  content: string;
  encoding?: string | null;
  etag?: string | null;
  size?: number | null;
  mtime?: string | null;
  content_type?: string | null;
};
export type FileWriteResponse = components["schemas"]["FileWriteResponse"];
export type FileRenameResponse = components["schemas"]["FileRenameResponse"];
export type DirectoryWriteResponse = components["schemas"]["DirectoryWriteResponse"];
