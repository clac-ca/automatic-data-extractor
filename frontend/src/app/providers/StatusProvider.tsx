import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState
} from "react";

export type StatusKind = "upload" | "job" | "system";
export type StatusState = "pending" | "running" | "success" | "error";

export interface StatusEntry {
  readonly id: string;
  readonly label: string;
  readonly kind: StatusKind;
  readonly state: StatusState;
  readonly progress?: number;
  readonly metadata?: Record<string, string | number>;
}

interface UpsertStatusInput {
  readonly id: string;
  readonly label: string;
  readonly kind: StatusKind;
  readonly state: StatusState;
  readonly progress?: number;
  readonly metadata?: Record<string, string | number>;
}

interface StatusContextValue {
  readonly entries: StatusEntry[];
  readonly upsertStatus: (entry: UpsertStatusInput) => void;
  readonly removeStatus: (id: string) => void;
  readonly clearFinished: () => void;
}

const StatusContext = createContext<StatusContextValue | undefined>(undefined);

interface StatusProviderProps {
  readonly children: ReactNode;
}

export function StatusProvider({ children }: StatusProviderProps): JSX.Element {
  const [entries, setEntries] = useState<StatusEntry[]>([]);

  const upsertStatus = useCallback((entry: UpsertStatusInput) => {
    setEntries((current) => {
      const existingIndex = current.findIndex((item) => item.id === entry.id);
      const nextEntry: StatusEntry = { ...entry };

      if (existingIndex === -1) {
        return [...current, nextEntry];
      }

      const copy = [...current];
      copy[existingIndex] = nextEntry;
      return copy;
    });
  }, []);

  const removeStatus = useCallback((id: string) => {
    setEntries((current) => current.filter((item) => item.id !== id));
  }, []);

  const clearFinished = useCallback(() => {
    setEntries((current) => current.filter((item) => item.state === "running"));
  }, []);

  const value = useMemo<StatusContextValue>(
    () => ({ entries, upsertStatus, removeStatus, clearFinished }),
    [entries, upsertStatus, removeStatus, clearFinished]
  );

  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>;
}

export function useStatusContext(): StatusContextValue {
  const context = useContext(StatusContext);

  if (!context) {
    throw new Error("useStatusContext must be used within a StatusProvider");
  }

  return context;
}
