import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface SettingsSectionContextValue {
  readonly entityLabel: string | null;
  readonly setEntityLabel: (value: string | null) => void;
}

const SettingsSectionContext = createContext<SettingsSectionContextValue | null>(null);

export function SettingsSectionProvider({ children }: { readonly children: ReactNode }) {
  const [entityLabel, setEntityLabel] = useState<string | null>(null);

  const value = useMemo<SettingsSectionContextValue>(
    () => ({
      entityLabel,
      setEntityLabel,
    }),
    [entityLabel],
  );

  return <SettingsSectionContext.Provider value={value}>{children}</SettingsSectionContext.Provider>;
}

export function useOptionalSettingsSectionContext() {
  return useContext(SettingsSectionContext);
}
