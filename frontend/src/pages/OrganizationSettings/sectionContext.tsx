import { createContext, useContext, type ReactNode } from "react";

import type { OrganizationSettingsRouteId } from "./settingsNav";

type OrganizationSettingsSectionContextValue = {
  readonly sectionId: OrganizationSettingsRouteId;
  readonly params: readonly string[];
};

const OrganizationSettingsSectionContext = createContext<OrganizationSettingsSectionContextValue | null>(null);

export function OrganizationSettingsSectionProvider({
  value,
  children,
}: {
  readonly value: OrganizationSettingsSectionContextValue;
  readonly children: ReactNode;
}) {
  return (
    <OrganizationSettingsSectionContext.Provider value={value}>
      {children}
    </OrganizationSettingsSectionContext.Provider>
  );
}

export function useOrganizationSettingsSection(): OrganizationSettingsSectionContextValue {
  const context = useContext(OrganizationSettingsSectionContext);
  if (!context) {
    throw new Error("useOrganizationSettingsSection must be used within OrganizationSettingsSectionProvider");
  }
  return context;
}
