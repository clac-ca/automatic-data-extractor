import type { components } from "@schema";

export type DocumentListRow = components["schemas"]["DocumentListRow"];

export type DocumentsListParams = {
  perPage: number;
  sort: string | null;
  filters: string | null;
  joinOperator: "and" | "or" | null;
  q: string | null;
};
