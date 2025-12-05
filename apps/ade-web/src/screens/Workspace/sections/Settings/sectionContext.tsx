import { createContext, useContext, type ReactNode } from "react";

import type { WorkspaceSettingsRouteId } from "./settingsNav";

type SettingsSectionContextValue = {
  readonly sectionId: WorkspaceSettingsRouteId;
  readonly params: readonly string[];
};

const SettingsSectionContext = createContext<SettingsSectionContextValue | null>(null);

export function SettingsSectionProvider({
  value,
  children,
}: {
  readonly value: SettingsSectionContextValue;
  readonly children: ReactNode;
}) {
  return <SettingsSectionContext.Provider value={value}>{children}</SettingsSectionContext.Provider>;
}

export function useSettingsSection(): SettingsSectionContextValue {
  const ctx = useContext(SettingsSectionContext);
  if (!ctx) {
    throw new Error("useSettingsSection must be used within a SettingsSectionProvider");
  }
  return ctx;
}
