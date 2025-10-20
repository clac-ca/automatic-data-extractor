import type { components } from "@api-types";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type UserProfile = Schema<"UserProfile">;

export type UserSummary = Schema<"UserSummary">;
