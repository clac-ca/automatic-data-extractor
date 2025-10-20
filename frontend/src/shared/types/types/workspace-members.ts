import type { components } from "@types/api";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type WorkspaceMember = Schema<"WorkspaceMember">;
