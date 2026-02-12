import type { ReactNode } from "react";

export type SettingsSortOrder = "asc" | "desc";

export interface SettingsListState {
  readonly q: string;
  readonly sort: string;
  readonly order: SettingsSortOrder;
  readonly page: number;
  readonly pageSize: number;
  readonly filters: Record<string, string>;
}

export interface SettingsTableColumnSpec<T> {
  readonly id: string;
  readonly header: ReactNode;
  readonly cell: (row: T) => ReactNode;
  readonly headerClassName?: string;
  readonly cellClassName?: string;
}

export interface SettingsFormErrorSummaryItem {
  readonly key: string;
  readonly label: string;
  readonly message: string;
  readonly fieldId?: string;
}

export interface SettingsFormErrorSummaryModel {
  readonly title?: string;
  readonly items: readonly SettingsFormErrorSummaryItem[];
}

export interface SettingsMutationState {
  readonly status: "idle" | "pending" | "success" | "error";
  readonly message: string | null;
}

export interface SettingsSectionSpec {
  readonly id: string;
  readonly label: string;
  readonly visible?: boolean;
  readonly tone?: "default" | "danger";
}

export interface SettingsSectionNavModel {
  readonly sections: readonly SettingsSectionSpec[];
  readonly activeSectionId: string | null;
}
