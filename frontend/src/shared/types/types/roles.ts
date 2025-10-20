import type { components } from "@api-types";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type PermissionDefinition = Schema<"PermissionRead">;

export type RoleDefinition = Schema<"RoleRead">;

export type RoleCreatePayload = Schema<"RoleCreate">;

export type RoleUpdatePayload = Schema<"RoleUpdate">;
