/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, type ReactNode } from "react";

import type { SessionEnvelope } from "../../../shared/types/auth";

type RefetchSession = () => Promise<unknown>;

export interface SessionContextValue {
  readonly session: SessionEnvelope;
  readonly refetch: RefetchSession;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export interface SessionProviderProps {
  readonly session: SessionEnvelope;
  readonly refetch: RefetchSession;
  readonly children: ReactNode;
}

export function SessionProvider({ session, refetch, children }: SessionProviderProps) {
  return (
    <SessionContext.Provider value={{ session, refetch }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionContext(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionContext must be used within a SessionProvider");
  }
  return context;
}

export function useSession() {
  return useSessionContext().session;
}

export function useSessionRefetch() {
  return useSessionContext().refetch;
}
