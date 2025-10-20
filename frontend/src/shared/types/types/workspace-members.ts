import type { components } from "@api-types";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type WorkspaceMember = Schema<"WorkspaceMember">;
