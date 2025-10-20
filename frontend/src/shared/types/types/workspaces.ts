import type { components } from "@types/api";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type WorkspaceApiProfile = Schema<"WorkspaceProfile">;

export type WorkspaceCreatePayload = Schema<"WorkspaceCreate">;

export type WorkspaceUpdatePayload = Schema<"WorkspaceUpdate">;

export type WorkspaceDefaultSelection = Schema<"WorkspaceDefaultSelection">;

export interface WorkspaceProfile {
  id: string;
  name: string;
  slug: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
}
